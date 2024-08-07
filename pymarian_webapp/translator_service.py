from functools import lru_cache
from itertools import zip_longest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sentence_splitter
from pymarian import Translator

from . import log
from .constants import BASE_ARGS, DEF_FLICKER_SIZE
from .mtapi_client import MTAPIClient


class TranslatorService:

    def __init__(self, mt_models: Dict[str, Dict[str, str]], eager_load=False) -> None:
        self.known_models = {}  # base case: no known models; not using MT service

        if mt_models:
            self.known_models = mt_models
        self.cache: Dict[str, Translator] = {}

        if eager_load:
            for model_name in self.known_models:
                self.get_model(model_name)
        # TODO: retrieve language ID from config file
        self.sentence_splitter = sentence_splitter.SentenceSplitter(language="en")

    def sentence_split(self, text: str) -> List[str]:
        return self.sentence_splitter.split(text)

    def tokenize(self, text: str) -> List[str]:
        # TODO: support tokenization using sentence piece model used by Marian
        return text.split()

    def detokenize(self, text: List[str]) -> str:
        return " ".join(text)

    def get_model(self, model_name) -> Translator:
        """
        Instantiate a model if not already in cache.
        """
        if model_name not in self.cache:
            log.warning(
                f"Model name '{model_name}' not in cache. Going to initialize. Currently cached models are {self.cache.keys()}"
            )
            assert (
                model_name in self.known_models
            ), f"Unknown model {model_name}. Known models are {self.known_models}"
            model = self.known_models[model_name]

            model_type = model.get("type", None)

            if model_type == "mtapi":
                for key in ["subscription-key", "source-language", "target-language"]:
                    assert key in model, f"'{key}' is required for model type 'mtapi'"

                log.info(f"Creating MTAPI translator")
                self.cache[model_name] = MTAPIClient(
                    srcLang=model["source-language"],
                    trgLang=model["target-language"],
                    subscription_key=model["subscription-key"],
                )

            else:
                assert model_type in (
                    "base",
                ), f"Unknown model type '{model_type}'. Known types are 'base', or 'mtapi'"
                for key in ["model"]:
                    assert key in model, f"'{key}' is required for model type 'mttruck' or 'base'"

                model_path = Path(model["model"])
                vocab_path = Path(model["vocab"]) if "vocab" in model else model_path.parent / "vocab.spm"

                assert (
                    model_path.exists() and model_path.is_file()
                ), f"Model path '{model_path}' does not exist"
                assert vocab_path.exists(), f"Vocab path '{vocab_path}' does not exist"
                mt_args = BASE_ARGS | dict(
                    models=str(model_path),
                    vocabs=[str(vocab_path), str(vocab_path)],
                    # TODO: allow to override these options in the config file
                    beam_size=1,
                    normalize=1,
                    maxi_batch=1,
                    mini_batch=1,
                    # output_approx_knn=(128, 1024)  # FIXME this crashes --force-decode
                )

                log.info(f"Creating translator with args:\n {mt_args}")
                translator = Translator(**mt_args)

                sentence_breaking = model.get("sentence_breaking", False)
                doc_enabled = model.get("doc_enabled", False)

                if sentence_breaking or doc_enabled:
                    sentence_join_token = model.get("sentence_join_token", " [eos]")
                    sb_args = dict(
                        translator=translator,
                        doc_enabled=doc_enabled,
                        sentence_join_token=sentence_join_token,
                    )
                    self.cache[model_name] = SentenceBreakerWrapper(**sb_args)
                else:
                    self.cache[model_name] = translator

        return self.cache[model_name]

    def translate(self, model_name:str, sources:List[str]) -> List[str]:
        """
        Example output format:
        {
            "sources": [ "Hi" ],
            "time_taken": 2.254,
            "time_units": "s",
            "translations": [
                {
                    "name": "standard",
                    "outputs": [ "Hallo" ],
                    "source": [ "Hi" ]
                },
                {
                    "name": "formal",
                    "outputs": [ "Hallo" ],
                    "source": [ "<instruction> formal </instruction> Hi" ]
                },
                {
                    "name": "informal",
                    "outputs": [ "Hallo" ],
                    "source": [ "<instruction> informal </instruction> Hi" ]
                }]
            }
        }
        """
        log.info(f"Translating '{sources}' using '{model_name}'")
        translator = self.get_model(model_name)
        return [{"outputs": translator.translate(sources)}]

    def force_decode_batch(
        self, model_name: str, sources: List[str], prefixes: Optional[List[str]] = None
        ) -> List[str]:
        """Force decode with prefixes
        :param model_name: model name
        :param sources: list of source sentences
        :param prefixes: list of prefixes
        :return: list of translations
        """
        translator = self.get_model(model_name)
        if not prefixes or len(prefixes) == 1 and not prefixes[0]:
            log.info(f"Decoding without prefixes (no force decode): \n {sources}")
            result = translator.translate(sources)
        else:
            assert len(sources) == len(
                prefixes
            ), f"Length of sources and prefixes should be the same. Got {sources} and {prefixes}"
            sources = [
                '%s\t%s' % (source.replace('\t', ' ').rstrip(), prefix.replace('\t', ' ').rstrip())
                for source, prefix in zip(sources, prefixes)
            ]
            log.info(f"Force decoding with sources:\n {sources}")
            result = translator.translate(sources, force_decode=True, tsv=True, tsv_fields=2)

        return result

    @lru_cache(maxsize=1024)
    def force_decode(self, model_name: str, source: str, prefix: str) -> str:
        """Force decode with prefix. Supports caching of args.

        :param model_name: model name
        :param source: source sentence
        :param prefix: prefix
        :return: translation
        """
        translator = self.get_model(model_name)
        if not prefix:
            log.info(f"Decoding without prefix (no force decode): \n {source}")
            result = translator.translate(source)
        else:
            source = source.replace('\t', ' ').rstrip()
            prefix = prefix.replace('\t', ' ').rstrip()
            source = f"{source}\t{prefix}"
            log.info(f"Force decoding with source:\n {source}")
            result = translator.translate(source, force_decode=True, tsv=True, tsv_fields=2)
        return result

    def _flicker_sentence(self, sentence: str, flicker_size: int) -> str:
        """Flicker the sentence by removing flicker_size tokens from the end

        :param sentence: sentence
        :param flicker_size: size of flicker; number of tokens
        :return: flickered sentence
        """
        assert flicker_size > 0, f"Flicker size should be greater than 0. Got {flicker_size}"
        return self.detokenize(self.tokenize(sentence)[:-flicker_size])

    def live_translate(
        self, model_name: str, source: str, target_segments: List[str], flicker_size=DEF_FLICKER_SIZE
    ) -> str:
        """Live translation with prefix caching and flickering (last) target sentence

        :param model_name: model name
        :param source: source sentence
        :param target_segments: target segments (i.e., sentences that align 1:1 with source segments)
        :param flicker_size: size of flicker; number of tokens
        :return: translated sentence
        """
        assert source, "Source should not be empty"

        rows = []
        source_sents = self.sentence_split(source)
        target_segments = (target_segments or [])[: len(source_sents)]  # ignore extra target sentences

        last_tgt_idx = -1
        for idx, (src, tgt) in enumerate(zip_longest(source_sents, target_segments)):
            rows.append([src, tgt])
            if tgt:  # not empty,  not None
                last_tgt_idx = idx

        if flicker_size > 0 and last_tgt_idx >= 0:
            # flicker the last tgt sentence
            last_tgt_segment = rows[last_tgt_idx][1]
            rows[last_tgt_idx][1] = self._flicker_sentence(last_tgt_segment, flicker_size)

        src_segs_out = []
        tgt_segs_out = []
        for idx, (src, tgt) in enumerate(rows):
            src_segs_out.append(src)
            if tgt and last_tgt_idx >= 0 and idx < last_tgt_idx:  # reuse prior translations
                tgt_segs_out.append(tgt)
            else:  # fresh translation
                tgt_segs_out.append(self.force_decode(model_name, src, tgt))  # assumption: cached
                # TODO: support batching
        return src_segs_out, tgt_segs_out


class SentenceBreakerWrapper:
    def __init__(self, translator=None, language="en", **kwargs):
        self.translator = translator
        log.info(f"Creating sentence breaker for language '{language}'")
        self.splitter = sentence_splitter.SentenceSplitter(language=language)

        self.doc_enabled = kwargs.get("doc_enabled", False)
        self.sentence_join_token = kwargs.get("sentence_join_token", None)

    def translate(self, sources: List[str]) -> List[str]:
        if self.doc_enabled:
            # for doc models, sentence-split, but then join by [eos] within each original line
            sources = [self.sentence_join_token.join(self.splitter.split(s)) for s in sources]
            log.info(f"Combined source sentences into: {sources}")
            translations = self.translator.translate(sources)
            translations = [" ".join(translations[0].split(self.sentence_join_token))]
        else:
            # otherwise, split on sentences, but maintain the original boundaries
            sources = [self.splitter.split(s) for s in sources]
            log.info(f"Split source sentences into: {sources}")
            lens = [len(s) for s in sources]
            # flatten the list of lists
            sources = [s for sublist in sources for s in sublist]
            translations = self.translator.translate(sources)
            # unflatten the list of lists
            translations = [translations[i : i + l] for i, l in enumerate(lens)]
        return translations

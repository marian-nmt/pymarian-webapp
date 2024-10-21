from functools import lru_cache
from itertools import zip_longest
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pymarian import Evaluator, Defaults
from pymarian.utils import get_model_path, get_vocab_path

from . import log
from .constants import BASE_ARGS, DEF_FLICKER_SIZE, CHOSEN_METRICS, DEF_EAGER_LOAD


@dataclass
class ModelMeta:
    name: str
    like: str
    model_id: str
    model_path: Path
    vocab_path: Path

class EvaluatorService:

    def __init__(self, names: List[str] = CHOSEN_METRICS, eager_load=DEF_EAGER_LOAD) -> None:
        self.known_models = self.download_models(names)
        self.cache: Dict[str, Evaluator] = {}
        if eager_load:
            self.load_all()

    @staticmethod
    def download_models(names:List[str]) -> Dict[str, ModelMeta]:
        metas = {}
        for name in names:
            assert name in Defaults.KNOWN_METRICS, \
                f"Unknown model {name}. Known models are {Defaults.KNOWN_METRICS}"
            model_type, hf_id = Defaults.KNOWN_METRICS[name]
            if model_type != "comet-qe":
                log.info(f"Skipping model {name} as it is not a comet-qe model")
                continue
            try:
                log.info(f"Caching model {name}")
                model_path = get_model_path(name)
                vocab_path = get_vocab_path(name)
                meta = ModelMeta(name=name, like=model_type, model_id=hf_id,
                                model_path=model_path, vocab_path=vocab_path)
                metas[name] = meta
            except Exception as e:
                log.warning(f"Failed to load model {name}: {e}")
                log.warning(f"Skipping model {name}")
                continue
        return metas

    def load_all(self):
        for model_name in self.known_models:
            try:
                self.get_model(model_name)
            except Exception as e:
                log.warning(f"Failed to load model {model_name}: {e}")
                self.known_models.pop(model_name, None)
                continue

    def get_model(self, model_name) -> Evaluator:
        """
        Instantiate a model if not already in cache.
        """
        if model_name not in self.cache:
            log.warning(f"Model name '{model_name}' not in cache. Going to initialize."\
                f"Currently cached models are {self.cache.keys()}")
            assert model_name in self.known_models,\
                f"Unknown model {model_name}. Known models are {self.known_models}"
            meta = self.known_models[model_name]
            model_args = BASE_ARGS | dict(
                model_file=meta.model_path,
                vocab_file=meta.vocab_path,
                like = meta.like,
                fp16 = False,
            )
            log.info(f"Creating evaluator with args:\n {model_args}")
            evaluator = Evaluator.new(**model_args)
            self.cache[model_name] = evaluator
        return self.cache[model_name]

    def evaluate(self, model_name:str, sources:List[str], mts: List[str], refs: List[str]=None) -> float:
        assert not refs, f"Ref not supported and only QE models are supported at the moment" # future work
        log.info(f"Eval '{model_name}'; src:{sources}; mt:{mts}")
        assert sources and mts, f"Source and mt are required"
        assert len(sources) == len(mts), f"Source and mt must have the same length"
        rows = [f'{s}\t{t}' for (s,t) in zip(sources, mts)]
        evaluator = self.get_model(model_name)
        scores = list(evaluator.evaluate(rows))
        log.info(f"input: {rows}")
        log.info(f"score: {scores}")
        res = []
        for score in scores:
            # some metrics give forward and backward scores, we pick the first one
            if isinstance(score, (list, tuple)):
                score = score[0]
            res.append(score)
        return res

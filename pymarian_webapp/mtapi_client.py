#!/usr/bin/env python3
"""
Queries the MSFT MTAPI interface.
"""

import os
import uuid
from typing import List

import requests


class MTAPIClient:
    def __init__(self, srcLang="en", trgLang="de", region="eastus", subscription_key=None):
        self.srcLang = srcLang
        self.trgLang = trgLang
        self.region = os.environ.get("MTAPI_REGION", region)
        self.subscription_key = os.environ.get("MTAPI_SUBSCRIPTION_KEY", subscription_key)
        self.endpoint = "https://api.cognitive.microsofttranslator.com/translate"

    def get_headers(self):
        headers = {
            'Ocp-Apim-Subscription-Key': self.subscription_key,
            'Ocp-Apim-Subscription-Region': self.region,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4()),
        }

        return headers

    def translate(self, text: List[str]) -> List[str]:
        """
        Gets translation(s) for a list of sentences.
        """
        params = {
            'api-version': '3.0',
            'to': [self.trgLang],
        }
        if self.srcLang is not None:
            params["from"] = self.srcLang

        body = [{'text': text} for text in text]
        request = requests.post(self.endpoint, params=params, headers=self.get_headers(), json=body)
        response = request.json()

        translations = []

        for sent in response:
            translations.append([translation["text"] for translation in sent["translations"]])

        return translations

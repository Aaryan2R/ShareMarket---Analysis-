# core/sentiment_engine.py

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np


class SentimentEngine:

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")

    def score(self, headlines):
        scores = []

        for text in headlines:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True)
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1).detach().numpy()[0]
            sentiment_score = probs[2] - probs[0]  # positive - negative
            scores.append(sentiment_score)

        avg_score = np.mean(scores) if scores else 0

        if avg_score > 0.2:
            label = "Positive"
        elif avg_score < -0.2:
            label = "Negative"
        else:
            label = "Neutral"

        return round(float(avg_score), 3), label
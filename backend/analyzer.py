import re
import nltk
from nltk.corpus import stopwords
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Download necessary NLTK data
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class PoliticalAnalyzer:
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words('english'))

    def clean_text(self, text):
        """Removes URLs, mentions, hashtags, and special characters."""
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        # Remove mentions (@user) and hashtags (#tag)
        text = re.sub(r'\@\w+|\#\w+', '', text)
        # Remove emojis and non-ascii
        text = text.encode('ascii', 'ignore').decode('ascii')
        # Remove special characters and numbers
        text = re.sub(r'[^a-zA-Z\s]', '', text)
        # Remove extra whitespace
        text = " ".join(text.split())
        
        return text

    def get_sentiment(self, text):
        """Returns a sentiment dictionary with specialized scores."""
        cleaned = self.clean_text(text)
        if not cleaned:
            return {"sentiment": "neutral", "score": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0}
        
        scores = self.sia.polarity_scores(cleaned)
        compound = scores['compound']
        
        if compound >= 0.05:
            sentiment = "positive"
        elif compound <= -0.05:
            sentiment = "negative"
        else:
            sentiment = "neutral"
            
        return {
            "sentiment": sentiment,
            "score": compound,
            "positive": scores['pos'],
            "negative": scores['neg'],
            "neutral": scores['neu']
        }

if __name__ == "__main__":
    analyzer = PoliticalAnalyzer()
    test_texts = [
        "The new policy is an absolute disaster for the economy! #FailedState",
        "I am very optimistic about the upcoming election, things are looking up.",
        "The debate happened yesterday at 8 PM."
    ]
    for t in test_texts:
        print(f"Text: {t}")
        print(f"Result: {analyzer.get_sentiment(t)}\n")

from flask import Flask, request, jsonify, render_template, redirect, url_for
import praw
from transformers import pipeline
from flask_cors import CORS
import re
from playwright.sync_api import sync_playwright
import jmespath
import requests

app = Flask(__name__)
CORS(app)

# Reddit API client setup
reddit = praw.Reddit(
    client_id='LChxVKKanHy2xEOwKnpDxQ',
    client_secret='RgtMN6iE-bkUi8wd6QbaQEiCM2SYCg',
    user_agent='Competitive-Judge236'
)

# Sentiment analysis model setup
sentiment_model = pipeline(
    "sentiment-analysis",
    model="PRAli22/AraBert-Arabic-Sentiment-Analysis"
)

def normalize_text(text):
    """Normalize text: convert to lowercase and remove punctuation."""
    text = text.lower()
    text = re.sub(r'[^\u0600-\u06FF\s]', '', text)
    return text

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    if request.method == 'POST':
        search_query = request.form.get('query')
        search_type = request.form.get('type')
        limit = request.form.get('limit', default=20, type=int)

        if not search_query:
            return jsonify({'error': 'No query provided. Please specify a query.'}), 400

        if limit < 1:
            return jsonify({'error': 'Invalid limit value. Please specify a positive integer.'}), 400

        subreddit_to_search = 'all'
        if search_type == 'sport':
            subreddit_to_search = 'sports'

        submissions = reddit.subreddit(subreddit_to_search).search(search_query, limit=limit, time_filter='week')

        title_ratings = []
        recent_titles = []
        total_rating = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        positive_scores = []
        neutral_scores = []
        negative_scores = []

        for submission in submissions:
            title = submission.title
            normalized_title = normalize_text(title)
            result = sentiment_model(normalized_title)
            label = result[0]['label'].lower()
            score = result[0]['score']

            positive_scores.append(score if label == 'positive' else 0)
            neutral_scores.append(score if label == 'neutral' else 0)
            negative_scores.append(score if label == 'negative' else 0)

            total_rating[label] += 1

            author_username = submission.author.name if submission.author else 'Unknown'
            author_profile_picture = submission.author.icon_img if submission.author and submission.author.icon_img else ''

            title_ratings.append({
                'title': title,
                'label': label,
                'score': score,
                'author': {
                    'username': author_username,
                    'profile_picture': author_profile_picture
                }
            })

            recent_titles.append(title)
        
        total_submissions = limit
        sentiment_percentages = {
            'positive': (total_rating['positive'] / total_submissions) * 100 if total_submissions > 0 else 0,
            'negative': (total_rating['negative'] / total_submissions) * 100 if total_submissions > 0 else 0,
            'neutral': (total_rating['neutral'] / total_submissions) * 100 if total_submissions > 0 else 0
        }

        response = {
            'title_ratings': title_ratings,
            'total_rating': total_rating,
            'recent_titles': recent_titles,
            'sentiment_percentages': sentiment_percentages,
            'positive_scores': positive_scores,
            'neutral_scores': neutral_scores,
            'negative_scores': negative_scores
        }

        return render_template('result.html', response=response)



# Updated API URL
API_URL = "https://api-inference.huggingface.co/models/Abdou/arabert-base-algerian"
headers = {"Authorization": "Bearer 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"}

def scrape_tweet(url: str) -> dict:
    _xhr_calls = []

    def intercept_response(response):
        if response.request.resource_type == "xhr":
            _xhr_calls.append(response)
        return response

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on("response", intercept_response)
        page.goto(url)
        page.wait_for_selector("[data-testid='tweet']")
        tweet_calls = [f for f in _xhr_calls if "TweetResultByRestId" in f.url]
        for xhr in tweet_calls:
            data = xhr.json()
            return data['data']['tweetResult']['result']

def parse_tweet(data):
    result = jmespath.search(
        """{
        created_at: legacy.created_at,
        attached_urls: legacy.entities.urls[].expanded_url,
        attached_urls2: legacy.entities.url.urls[].expanded_url,
        attached_media: legacy.entities.media[].media_url_https,
        tagged_users: legacy.entities.user_mentions[].screen_name,
        tagged_hashtags: legacy.entities.hashtags[].text,
        favorite_count: legacy.favorite_count,
        bookmark_count: legacy.bookmark_count,
        quote_count: legacy.quote_count,
        reply_count: legacy.reply_count,
        retweet_count: legacy.retweet_count,
        quote_count: legacy.quote_count,
        text: legacy.full_text,
        is_quote: legacy.is_quote_status,
        is_retweet: legacy.retweeted,
        language: legacy.lang,
        user_id: legacy.user_id_str,
        id: legacy.id_str,
        conversation_id: legacy.conversation_id_str,
        source: source,
        views: views.count
    }""",
        data,
    )
    result["poll"] = {}
    poll_data = jmespath.search("card.legacy.binding_values", data) or []
    for poll_entry in poll_data:
        key, value = poll_entry["key"], poll_entry["value"]
        if "choice" in key:
            result["poll"][key] = value["string_value"]
        elif "end_datetime" in key:
            result["poll"]["end"] = value["string_value"]
        elif "last_updated_datetime" in key:
            result["poll"]["updated"] = value["string_value"]
        elif "counts_are_final" in key:
            result["poll"]["ended"] = value["boolean_value"]
        elif "duration_minutes" in key:
            result["poll"]["duration"] = value["string_value"]
    user_data = jmespath.search("core.user_results.result", data)
    if user_data:
        result["user"] = ''
    return result

def scrape_twitter(url):
    data = parse_tweet(scrape_tweet(url))
    return data['text']

def sentiment_analysis(text):
    output = query({"inputs": text})
    return output[0]

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'url' in request.form:
            url = request.form['url']
            return redirect(url_for('twitter_page', url=url))
        elif 'text' in request.form:
            text = request.form['text']
            return redirect(url_for('text_analysis', text=text))
    return render_template('index.html')

@app.route('/twitter')
def twitter_page():
    url = request.args.get('url')
    if url:
        try:
            text = scrape_twitter(url)
            sentiment = sentiment_analysis(text)
        except KeyError:
            sentiment = [{'label': 'neutral', 'score': 0}, {'label': 'positive', 'score': 0}, {'label': 'negative', 'score': 0}]
            text = 'Server is starting, please try again after 20 seconds.'
        except:
            sentiment = [{'label': 'neutral', 'score': 0}, {'label': 'positive', 'score': 0}, {'label': 'negative', 'score': 0}]
            text = 'Invalid URL, please enter a valid URL.'
        return render_template('twitter.html', sentiment_result=sentiment, tweet_text=text)
    return render_template('twitter.html')

@app.route('/text_analysis')
def text_analysis():
    text = request.args.get('text')
    if text:
        sentiment = sentiment_analysis(text)
        return render_template('result2.html', text=text, sentiment_result=sentiment)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

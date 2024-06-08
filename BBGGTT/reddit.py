def fetch_reddit_data(reddit, sentiment_model, search_query, search_type, limit):
    subreddit_to_search = 'all'
    if search_type == 'sport':
        subreddit_to_search = 'sports'

    submissions = reddit.subreddit(subreddit_to_search).search(search_query, limit=limit, time_filter='week')

    title_ratings = []
    recent_titles = []
    total_rating = {'positive': 0, 'negative': 0, 'neutral': 0}

    for submission in submissions:
        title = submission.title
        normalized_title = normalize_text(title)
        result = sentiment_model(normalized_title)
        label = result[0]['label'].lower()
        total_rating[label] += 1

        author_username = submission.author.name if submission.author else 'Unknown'
        author_profile_picture = submission.author.icon_img if submission.author and submission.author.icon_img else ''

        title_ratings.append({
            'title': title,
            'label': label,
            'score': result[0]['score'],
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
        'sentiment_percentages': sentiment_percentages
    }

    return response

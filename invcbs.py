"""
Fuzzy & semantic caption-based searching for YouTube videos.

"""
from collections             import defaultdict

import warnings
import argparse
import re
import gensim

from gensim.utils            import tokenize
from fuzzywuzzy              import process
from youtube_transcript_api  import YouTubeTranscriptApi
from nltk.corpus             import brown

warnings.filterwarnings("ignore")


def normalize_time(timestamps):
    normalized_time = []

    for timestamp in timestamps:
        seconds = int(timestamp)
        minutes = seconds//60
        hours = minutes//60
        minutes = minutes%60
        seconds = seconds%60

        normalized_timestamp = ''

        if hours != 0:
            normalized_timestamp += str(hours) + 'h '
        normalized_timestamp += str(minutes)+'m '+str(seconds)+'s'

        normalized_time.append(normalized_timestamp)

    return normalized_time


def pretty_print(output):

    spaces = max([len(caption) for caption, timestamp in output])
    spaces += 5
    for caption, timestamp in output:
        print(caption, end=' '*(spaces - len(caption)))
        print(timestamp)


def parse(large_dataset_filepath):

    _f_ = open(large_dataset_filepath)
    corpus = _f_.readlines()
    return corpus

def setup(small_dataset=True):
    
    sentences = ['']

    if small_dataset:
        sentences = brown.sents()
        model = gensim.models.Word2Vec(sentences, min_count=1)
    else:
        large_dataset_filepath = input('Enter your dataset\'s filepath: ')
        sentences = parse(large_dataset_filepath)
        model = gensim.models.Word2Vec(sentences, min_count=1)

    vocabulary = defaultdict(int)
    for sentence in sentences:
        for word in sentence:
            vocabulary[word] = 1

    return model, vocabulary


def get_video_id(youtube_video_url):

    # Regular expressions to parse YouTube links
    youtube = r'(youtu.be\/|v\/|e\/|u\/\w+\/|embed\/|v=)'
    video_id = r'([^#\&\?]*).*'
    https = r'^.*'

    parsed_url = re.search(https + youtube + video_id, youtube_video_url)

    return parsed_url[2]


def get_youtube_captions(youtube_video_url, languages=None):
    
    if languages is None:
        languages = ['en']

    video_id = get_video_id(youtube_video_url)

    captions_and_timestamps = dict()

    try:
        captions_and_timestamps = YouTubeTranscriptApi.get_transcript(video_id, languages)
    except Exception as _e_:
        # This exception arises in case of a broken link or when
        # searching in a video where captions are unavailable
        print(_e_, type(_e_))

    captions = defaultdict(float)

    for data in captions_and_timestamps:
        captions[data['text'].lower()] = data['start']

    return captions


class INVCBS:
    
    def __init__(self, small_dataset=True):
        """
        Class constructor.
        Defines and declares all variables used.

        """
        self._fuzzy_ = "FUZZY"
        self._semantic_ = "SEMANTIC"

        _m_, _v_ = setup(small_dataset=small_dataset)

        self.model, self.vocabulary = _m_, _v_


    def get_captions_by_fuzzy_similarity(self, query, corpus, limit=5):
        
        similar_strings = process.extractBests(query, corpus, limit=limit)
        reqd_strings = [caption for caption, similarity in similar_strings]

        return reqd_strings


    def get_captions_by_semantic_similarity(self, query, corpus, limit=5):
        
        captions_and_similarities = []

        corpus = list(corpus)

        for idx, caption in enumerate(corpus):
            similarity = self.compute_semantic_similarity(query, caption)
            captions_and_similarities.append([similarity, idx])

        captions_and_similarities.sort()
        captions_and_similarities = captions_and_similarities[:limit]

        closest_captions = []

        for similarity, idx in captions_and_similarities:
            closest_captions.append(corpus[idx])

        return closest_captions

    #sentence1 -> query, sentence2 -> sentence in captions
    def compute_semantic_similarity(self, sentence_1, sentence_2):
        
        sentence_1 = list(tokenize(sentence_1))
        sentence_2 = list(tokenize(sentence_2))

        visited_1 = [0]*len(sentence_1)
        visited_2 = [0]*len(sentence_2)

        similarity = 0

        # use cosine distance to compute similarity.
        for idx_a, word_a in enumerate(sentence_1):
            if self.vocabulary[word_a] == 1:
                visited_1[idx_a] = 1
                closest_distance = 1e18
                idx_chosen = -1
                for idx_b, word_b in enumerate(sentence_2):
                    if visited_2[idx_b] == 0 and self.vocabulary[word_b] == 1:
                        current_distance = (1 - self.model.similarity(word_a, word_b))
                        if idx_chosen == -1 or current_distance < closest_distance:
                            closest_distance = min(closest_distance, current_distance)
                            idx_chosen = idx_b

                if idx_chosen != -1:
                    visited_2[idx_chosen] = 1

                similarity += closest_distance

        return similarity/len(sentence_1)


    def get_timestamp(self, query, caption_to_timestamp, mode='FUZZY', limit=5):
        
        if mode == self._fuzzy_:
            get_captions = self.get_captions_by_fuzzy_similarity
            most_similar_captions = get_captions(query,
                                                 caption_to_timestamp.keys(),
                                                 limit=limit)

        elif mode == self._semantic_:
            get_captions = self.get_captions_by_semantic_similarity
            most_similar_captions = get_captions(query,
                                                 caption_to_timestamp.keys(),
                                                 limit=limit)

        marked_timestamps = [caption_to_timestamp[caption] for caption in most_similar_captions]

        return marked_timestamps


    def main(self, youtube_video_url, query, limit=5, languages=None, mode='FUZZY'):
        
        query = query.lower()
        captions_and_timestamps = get_youtube_captions(youtube_video_url, languages)

        timestamps = self.get_timestamp(query, captions_and_timestamps,
                                        limit=limit, mode=mode)

        timestamps_and_captions = defaultdict(str)

        for caption in captions_and_timestamps:
            key = captions_and_timestamps[caption]
            value = caption
            timestamps_and_captions[key] = value

        captions_extracted = []
        for timestamp in timestamps:
            captions_extracted.append(timestamps_and_captions[timestamp])

        pretty_print(list(zip(captions_extracted, normalize_time(timestamps))))
        return list(zip(captions_extracted, normalize_time(timestamps)))


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()

    PARSER.add_argument('--video', action='append')
    PARSER.add_argument('--mode', action='append',
                        choices=['FUZZY', 'SEMANTIC', 'F', 'S'])
    PARSER.add_argument('--limit', action='append')
    PARSER.add_argument('--language', action='append')
    ARGS = PARSER.parse_args()

    if ARGS.video is None:
        print('No video URL found.')
        exit()
    else:
        VIDEO = str(ARGS.video[0])

    if ARGS.mode is None:
        MODE = 'FUZZY'
    else:
        MODE = ARGS.mode[0]

    if ARGS.language is None:
        LANGUAGE = ['en']
    else:
        LANGUAGE = ARGS.language

    if ARGS.limit is None:
        LIMIT = 10
    else:
        LIMIT = int(ARGS.limit[0])

    query = input('Enter query string: ')

    FINDER = INVCBS()
    FINDER.main(VIDEO, query=query, limit=LIMIT, languages=LANGUAGE, mode=MODE)

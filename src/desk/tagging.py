"""Explainable topic tagging: an item joins a topic when one of the topic's keyword lines
appears in its title or summary as a whole word or phrase. Items that match nothing stay
untagged; nothing is inferred.
"""
import re

from .models import Topic


def _pattern(phrase):
    phrase = phrase.strip()
    escaped = r"\s+".join(re.escape(part) for part in phrase.split())
    flags = 0 if (phrase.isupper() and len(phrase) <= 5) else re.IGNORECASE
    return re.compile(rf"(?<!\w){escaped}(?!\w)", flags)


def compile_rules(topics=None):
    rules = []
    for topic in topics if topics is not None else Topic.objects.exclude(keywords=""):
        patterns = [_pattern(line) for line in topic.keywords.splitlines() if line.strip()]
        if patterns:
            rules.append((topic, patterns))
    return rules


def matching_topics(text, rules):
    return [topic for topic, patterns in rules if any(p.search(text) for p in patterns)]


def tag(item, text, rules):
    topics = matching_topics(text, rules)
    if topics:
        item.topics.add(*topics)
    return topics

import json


def extract_initial_state(html):
    start = html.find('window.__INITIAL_STATE__=JSON.parse("')
    if start == -1:
        raise ValueError("__INITIAL_STATE__ not found in page HTML")
    start += len('window.__INITIAL_STATE__=JSON.parse("')
    end = html.find('")', start)
    if end == -1:
        raise ValueError("Could not find closing of JSON.parse")
    raw = html[start:end]
    raw = raw.encode().decode("unicode_escape")
    return json.loads(raw)

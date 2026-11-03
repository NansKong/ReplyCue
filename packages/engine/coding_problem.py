"""Resolve explicit references against the problem publisher."""
import json
import re
from html import unescape
from urllib.request import Request, urlopen


def get_json(url, payload=None):
    body = json.dumps(payload).encode() if payload else None
    request = Request(url, data=body, headers={
        'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    with urlopen(request, timeout=4) as response:
        return json.loads(response.read(2_000_000))


def leetcode(query, **variables):
    return get_json('https://leetcode.com/graphql/', {
        'query': query, 'variables': variables,
    })['data']


def resolve_problem(turn):
    """Return statement data, None for ordinary turns, or raise on missing data."""
    match = re.search(r'\b(leet\s*code|code\s*chef)\b', turn, re.I)
    if not match:
        return None
    tail = turn[match.end():]
    if re.sub(r'\s', '', match[1].lower()) == 'leetcode':
        slug = re.search(r'leetcode\.com/problems/([a-z0-9-]+)', turn, re.I)
        number = re.search(r'\b[0-9]{1,5}\b', tail)
        if slug:
            name = slug[1]
        elif re.search(r'\bdaily\b', turn, re.I):
            daily = leetcode('{ activeDailyCodingChallengeQuestion { question { titleSlug } } }')
            name = daily['activeDailyCodingChallengeQuestion']['question']['titleSlug']
        elif number:
            result = leetcode(
                'query($filters: QuestionListFilterInput) { questionList(categorySlug: "", '
                'skip: 0, limit: 20, filters: $filters) { data { questionFrontendId titleSlug } } }',
                filters={'searchKeywords': number[0]})
            name = next(row['titleSlug'] for row in result['questionList']['data']
                        if row['questionFrontendId'] == number[0])
        else:
            return None
        data = leetcode(
            'query($slug: String!) { question(titleSlug: $slug) '
            '{ questionFrontendId title content isPaidOnly } }', slug=name)['question']
        if data['isPaidOnly'] or (number and not slug and not re.search(r'\bdaily\b', turn, re.I)
                                 and data['questionFrontendId'] != number[0]):
            raise ValueError('Problem unavailable')
        title = f"LeetCode {data['questionFrontendId']} · {data['title']}"
        url = f'https://leetcode.com/problems/{name}/'
        body = data['content']
    else:
        code = re.search(r'codechef\.com/problems/([a-z0-9_]+)', turn, re.I)
        if not code:
            code = re.search(r'\b([a-z][a-z0-9_]*\d[a-z0-9_]*)\b', tail, re.I)
        if not code:
            return None
        name = code[1].upper()
        data = get_json(f'https://www.codechef.com/api/contests/PRACTICE/problems/{name}')
        if data.get('problem_code') != name:
            raise ValueError('Problem unavailable')
        title, body = data['problem_name'], data['body']
        url = f'https://www.codechef.com/problems/{name}'
    if not body:
        raise ValueError('Problem statement unavailable')
    statement = unescape(re.sub(r'<[^>]+>', ' ', body)).strip()
    return {'title': title, 'url': url, 'statement': statement[:16000]}

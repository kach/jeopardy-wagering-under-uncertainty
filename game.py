SINGLE_JEOPARDY_CLUE_VALUES = [200, 400, 600, 800, 1000]
DOUBLE_JEOPARDY_CLUE_VALUES = [400, 800, 1200, 1600, 2000]
BOTTOM_BET = 1000
NUM_CATEGORIES = 6
NUM_CLUES_PER_CATEGORY = 5

SINGLE_JEOPARDY_TOTAL_MONEY = sum(SINGLE_JEOPARDY_CLUE_VALUES) * NUM_CATEGORIES
DOUBLE_JEOPARDY_TOTAL_MONEY = sum(DOUBLE_JEOPARDY_CLUE_VALUES) * NUM_CATEGORIES

PLAYERS = ['Harry', 'Ron', 'Hermione']

# J!-Archive parser

J_ROOT = 'http://www.j-archive.com/showgame.php?game_id='

def j_game_url(id):
    return J_ROOT + str(id)

def j_game_get(url):
    import requests
    return requests.get(url).text


def undollarify(x):
    return int(x.replace('DD: ', '').replace('$', '').replace(',', ''))

class Clue:
    def __init__(self, order, location, FJ, DD, value, grades):
        self.order = order
        self.location = location
        self.FJ = FJ
        self.DD = DD

        self.SJ = self.location.startswith('clue_J')
        self.DJ = self.location.startswith('clue_DJ')
        self.value = value
        self.grades = list(map(list, grades))

    def __str__(self):
        return '@' + self.location + ('*' if self.DD else '.')

def j_game_parse(text):
    from bs4 import BeautifulSoup
    import re
    SCORE_FINDER_RE = r'class="(wrong|right)">([A-Za-z]+)<'
    soup = BeautifulSoup(text, 'html.parser')
    out = []
    for td in soup.find_all('td', class_='clue'):
        loc = td.find('td', class_='clue_text')
        if loc is None:
            continue
        location = loc['id']
            
        fj_= td.find(id='clue_FJ')
        if fj_ is not None:
            value = None
            FJ = True
            DD = False
            order = -1
            w = soup.find('table', class_='final_round').find('div')['onmouseover']
            correctnesses = re.findall(SCORE_FINDER_RE, w)
            wagers = re.findall(r'\$[\d,]+', w)
            grades = [(grade, name, undollarify(wager)) for ((grade, name), wager) in zip(correctnesses, wagers)]
        else:
            FJ = False
            val = td.find('td', class_='clue_value')
            if val is not None:
                value = undollarify(val.text)
                DD = False
            else:
                value = undollarify(td.find('td', class_='clue_value_daily_double').text)
                DD = True
            order = int(td.find('td', class_='clue_order_number').find('a').text)
            w = td.find('div')['onmouseover']
            grades = re.findall(SCORE_FINDER_RE, w)
        clue = Clue(order, location, FJ, DD, value, grades)
        out.append(clue)
    return out

def j_get_players(db):
    for clue in db:
        if clue.FJ:
            g = clue.grades
            if len(g) != 3:
                exit(1)
            names = g[0][1], g[1][1], g[2][1]
            return names

def j_sort_db(db):
    sj = []
    dj = []
    fj = None
    db.sort(key=lambda x: x.order)
    players = j_get_players(db)
    for clue in db:
        for g in clue.grades:
            g[1] = PLAYERS[players.index(g[1])]
        if clue.FJ:
            fj = clue
        if clue.DJ:
            dj.append(clue)
        if clue.SJ:
            sj.append(clue)
    return sj + dj + [fj]

# for a sanity check
def j_play_game(db):
    scores = {PLAYERS[0]: 0, PLAYERS[1]: 0, PLAYERS[2]: 0}
    for clue in db:
        if clue.FJ:
            break
            for correctness, name, wager in clue.grades:
                scores[name] += wager if correctness == 'right' else -wager
        else:
            for correctness, name in clue.grades:
                if name not in scores:
                    scores[name] = 0
                scores[name] += clue.value if correctness == 'right' else -clue.value
    return scores

def j_evaluate_policies(db, dd_policies, fj_policies):
    scores = {}
    for i, clue in enumerate(db):
        if clue.FJ:
            break
            for correctness, name, wager in clue.grades:
                if name in fj_policies:
                    wager = fj_policies[name](db[:i+1], name)
                scores[name] += wager if correctness == 'right' else -wager
        else:
            for correctness, name in clue.grades:
                if name not in scores:
                    scores[name] = 0
                if name in dd_policies and clue.DD:
                    value = dd_policies[name](db[:i+1], name)
                    print('+', value, clue.value)
                else:
                    value = clue.value
                scores[name] += value if correctness == 'right' else -value
    return scores


def print_db(db):
    print('---')
    for clue in db:
        print(clue)
    print('---')

def utility(scores, player):
    s = sorted(scores.values())
    if scores[player] > s[1] * 2:
        return 1
    if s[2] > s[1] * 2:
        return -1
    return 0
#   return scores[player]





def policy(db_until_now, player):
    return policy_helper(db_until_now, player)[0]

def policy_helper(db_until_now, player):
    scores = j_play_game(db_until_now)
    if db_until_now[-1].FJ:
        return (None, utility(scores, player))

    g = GenerativeModel(db_until_now)
    a_star, v_star = None, float('-inf')
    N = 5
    k = 5
    for wager in np.random.uniform(low=0, high=max(1000, scores[player]), size=N):
        v = 0
        for _ in range(k):
            new_db = g.generate(wager)
            new_player = answerer(new_db[-1].grades) if not new_db[-1].FJ else player
            a_prime, v_prime = policy_helper(new_db, new_player)
            v += v_prime / k
        if v > v_star:
            a_star = wager
            v_star = v
    return (a_star, v_star)








ALL_CLUE_IDS = []
CLUE_VALUES = {}
for r in ['J', 'DJ']:
    for cat in range(NUM_CATEGORIES):
        for val in range(NUM_CLUES_PER_CATEGORY):
            clue_id = 'clue_%s_%d_%d' % (r, cat + 1, val + 1)
            ALL_CLUE_IDS.append(clue_id)
            if r == 'J':
                CLUE_VALUES[clue_id] = SINGLE_JEOPARDY_CLUE_VALUES[val]
            else:
                CLUE_VALUES[clue_id] = DOUBLE_JEOPARDY_CLUE_VALUES[val]

import itertools
RIGHT = +1
WRONG = -1
NOBUZ =  0
CLUE_OUTCOMES = list(itertools.product([RIGHT, WRONG, NOBUZ], repeat = 3))
CLUE_OUTCOMES = [o for o in CLUE_OUTCOMES if o.count(RIGHT) <= 1]

import copy
import random
import numpy as np
class GenerativeModel():
    def __init__(self, db_so_far):
        self.db_so_far = db_so_far
        self.remaining_clues = ALL_CLUE_IDS[:]
        self.clue_outcome_counts = {}
        for o in CLUE_OUTCOMES:
            self.clue_outcome_counts[o] = 0

        self.sj_dd_left = 1
        self.dj_dd_left = 2

        for clue in db_so_far:
            if clue.DD:
                if clue.location.startswith('clue_J'):
                    self.sj_dd_left -= 1
                else:
                    self.dj_dd_left -= 1
            else:
                outcome = [NOBUZ, NOBUZ, NOBUZ]
                for (c, name) in clue.grades:
                    outcome[PLAYERS.index(name)] = RIGHT if c == 'right' else WRONG
                outcome = tuple(outcome)
                self.clue_outcome_counts[outcome] += 1
            self.remaining_clues.remove(clue.location)

    def generate(self, wager):
        # generates a new transcript that has "advanced" until the next wagering event
        self.db_so_far[-1] = copy.deepcopy(self.db_so_far[-1])
        self.db_so_far[-1].value = wager
        db = self.db_so_far[:]
        sj = [c for c in self.remaining_clues if c.startswith('clue_J')]
        dj = [c for c in self.remaining_clues if c.startswith('clue_DJ')]

        if len(dj) != 30:
            sj = []
            self.sj_dd_left = 0

        random.shuffle(sj)
        random.shuffle(dj)

        sj_dd = random.sample(sj, self.sj_dd_left)
        dj_dd = random.sample(dj, self.dj_dd_left)

        dd = sj_dd + dj_dd
        clue_stream = sj + dj

        who = answerer(self.db_so_far[-1].grades)
        for loc in clue_stream:
            DD = loc in dd
            grades = []

            if DD:
                grades = [('right', who)]
            else:
                o = CLUE_OUTCOMES[ np.argmax( np.random.dirichlet( [self.clue_outcome_counts[o] + 1 for o in CLUE_OUTCOMES] ) ) ]
                for i in range(3):
                    name = PLAYERS[i]
                    if o[i] == NOBUZ:
                        continue
                    grades.append(('right' if o[i] == RIGHT else 'wrong', name))
                    if o[i] == RIGHT:
                        who = name
            clue = Clue(0, loc, FJ=False, DD=DD, value=CLUE_VALUES[loc], grades=grades)
            db.append(clue)
            if DD:
                return db

        clue = Clue(0, 'clue_FJ', FJ=True, DD=False, value=None, grades=[])
        db.append(clue)
        return db


def answerer(grades):
    right = [a[1] for a in grades if a[0] == 'right']
    if right == []:
        return None
    return right[0]

def is_runaway(scores):
    s = sorted(scores.values())
    return s[2] > s[1] * 2

from matplotlib import pyplot as plt
if __name__ == '__main__':
    import sys
    which = 'archives/archive-%s.html' % sys.argv[1]
    try:
        with open(which) as f:
            text = f.read()
            db = j_game_parse(text)
            db = j_sort_db(db)
            sa = j_evaluate_policies(db, {PLAYERS[0]: policy, PLAYERS[1]: policy, PLAYERS[2]: policy}, {})
            sh = j_play_game(db)

            print('*', is_runaway(sa), is_runaway(sh))

            for p in PLAYERS:
                print(sys.argv[1], sa[p], sh[p])
    except KeyboardInterrupt:
        exit(1)
    except Exception:
        pass

#j_play_game(j_sort_db(j_game_parse(j_game_get(j_game_url(6440)))))

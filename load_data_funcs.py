#-*- coding: utf-8 -*-
#common functions for loading data from vk

import hashlib
from nltk.stem.snowball import SnowballStemmer
import pickle
import os
import random
import string
import sys, traceback
import time
import requests
import tqdm

#can_see_audio
#hidden
#deactivated
#last_seen
#online,online_mobile,online_app
#timezone
#wall_comments
"""
getCommunityMembers
getMembersIntersection
getUsersInfo
transformUserInfo
loadAllCommunityMembers
"""

groups_of_interest={"sci":u"Science",
    "z_history":u"Empire History",
    "vk.fact":u"Знаете ли Вы?",
    "science_technology":u"Наука и Техника",
    "vk.krasota":u"Красиво сказано",
    "ilikes":u"Четкие Приколы",
    "mdk":u"MDK",
    "fuck_humor":u"ЁП",
    "evil_incorparate":u"Корпорация Зла",
    "tophumor":u"Чёрный юмор",
    "ifun":u"Смейся до слёз",
    "goodarts":u"Искусство реальности",
    "bez_kota":u"Без кота и жизнь не та",
    "cook_good":u"Лучшие рецепты",
    "lhack":u"Лайфхак",
    "fakt1":u"Интересные Факты",
    "academyofman":u"Академия Порядочных Парней",
    "strog_pocan":u"мужские мысли",
    "club_roditelej": u"НАШ КЛУБ для детей и родителей",
    "9o_6o_9o": u"Спортивные девушки",
    "my_sportt":u"Спорт - всегда в моде"}

def callApi(method,parameters):
    try:
        parameters['v'] = 5.53
        r = requests.post('https://api.vk.com/method/{0}'.format(method),data=parameters)
        if r.status_code != 200:
            raise Exception("status code:%s method:%s pars:%s" % (r.status_code,method,str(parameters)) )

        responce = r.json()
        if 'error' in responce:
            raise Exception(str(responce['error']))

        return responce

    except Exception as ex:
        raise type(ex)(ex.message + '%s %s' % (method,str(parameters)) )

def notFrequently(time_delta,func):
    class Wrapper:
        def __init__(self):
            self.lasr_call = time.time()
        def __call__(self,*args, **kwargs):
            if time.time() - self.lasr_call < time_delta:
                time.sleep(time_delta - (time.time() - self.lasr_call) )
            self.lasr_call = time.time()
            return func(*args, **kwargs)
    return Wrapper()

callApi = notFrequently(0.35, callApi)

def get_shuffled(list_,max_count=20000):
    for inx in range( min(max_count, len(list_)-2 ) ):
        inx2 = random.randrange(inx+1,len(list_))
        list_[inx],list_[inx2] = list_[inx2],list_[inx]
    return list_[:max_count]

def getCommunityMembers(community_id):
    count_in_community = callApi('groups.getMembers', {'group_id':community_id,'count':0})['response']['count']
    tqdm.tqdm.write("{} ids {}".format(count_in_community,community_id))
    count = 1000
    ids = []
    for i in tqdm.tnrange(count_in_community//1000 + 1, desc='get id list for %s'%community_id):
        if count == 1000:
            try:
                new_ids = callApi('groups.getMembers', {'group_id':community_id,'offset':len(ids)})['response']['items']
                ids += new_ids
                count = len(new_ids)
            except Exception as ex:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
                traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=sys.stdout)
                raise ex
        else:
            break

    return ids

def getMembersIntersection(user_ids,group_name):
    init_len = len(user_ids)
    intersection_ids = []
    for ids_subset in tqdm.tqdm_notebook([user_ids[i:i + 500] for i in range(0, len(user_ids), 500)], desc='inter for %s'%group_name):
        try:
            response = callApi('groups.isMember', {'group_id':group_name,'user_ids':",".join([ str(u) for u in ids_subset ])})['response']
            intersection_ids = intersection_ids + [ d['user_id'] for d in response if d['member'] == 1 ]
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
            traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=sys.stdout)
            raise ex
    return intersection_ids

def getUsersInfo(user_ids):
    users = []
    fields = """id,hidden,deactivated,id,sex, bdate, city, country,
                education,universities, schools, status, last_seen,
                followers_count, occupation, relation, personal,
                activities, interests, music, movies, tv, books,
                games,can_see_audio, career, military"""
    for ids_subset in [user_ids[i:i + 1000] for i in range(0, len(user_ids), 1000)]:
        try:

            response = callApi('users.get', {'user_ids':",".join([str(s) for s in ids_subset]),'fields':fields})['response']
            users += response
            #tqdm.tqdm.write("info loaded for %s , ids count %s"%(len(response),len(ids_subset)))
            #if(len(ids_subset)>len(response)):
            #    tqdm.tqdm.write("something strange happend!! resp less then request!")

        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
            traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=sys.stdout)
    return users

stemmer = SnowballStemmer("russian")
remove_punct = lambda s: "".join(" " if c in string.punctuation else c for c in s)
remove_space = lambda s: " ".join("".join(" " if c in string.whitespace else c for c in s).strip(' ').split())
stem = lambda s: stemmer.stem(s.lower())
full_clean = lambda s: stem(remove_space(remove_punct(s)))

def transformUserInfo(user_inf, groups_intersections = None):
    info = {}

    h = hashlib.sha256(str(user_inf['id']).encode())
    info['hash'] = h.hexdigest()[:20]

    if "deactivated" in user_inf:
        info["deactivated"] = user_inf["deactivated"]
    else:
        info["deactivated"] = ""

    if "hidden" in user_inf:
        info["hidden"] = user_inf["hidden"]
    else:
        info["hidden"] = ""

    info["sex"] = 'male' if user_inf["sex"] == 2 else 'female'
    if "bdate" in user_inf and len(user_inf["bdate"].split('.'))==3:
        age = 2017-int(user_inf["bdate"].split('.')[2])
        info["age"] = age
    if "city" in user_inf: info["city"] = user_inf["city"]['title']
    if "personal" in user_inf and "religion" in user_inf["personal"]:
        religion = full_clean(user_inf["personal"]["religion"])
        if religion in [u"православн",u"православный христианин"]: religion = u'православ'
        if religion in [u"Atheism",u"атеистическ",u"научный атеизм",u"атеист",u"научн"]: religion = u'атеизм'
        if religion in [u"агностик",u"агностицизм"]: religion = u"ангсоц"
        info["religion"] = religion
    if "personal" in user_inf and "life_main" in user_inf["personal"]:
        labels_d = {1:u"семья",2:u"карьера",3:u"развлечения",4:u"наука",5:u"соверш. мира",6:u"саморазвитие",7:u"искуство",8:u"власть"}
        info["life_main"] = labels_d[user_inf["personal"]["life_main"]]
    if "personal" in user_inf and "political" in user_inf["personal"] and user_inf["personal"]["political"]<10:
        labels_d = {
        1:u"коммунистические",
        2:u"социалистические",
        3:u"умеренные",
        4:u"либеральные",
        5:u"консервативные",
        6:u"монархические",
        7:u"ультраконсервативные",
        8:u"индифферентные",
        9:u"либертарианские"}
        info["political"] = labels_d[user_inf["personal"]["political"]]

    if "activities" in user_inf:
        info["activities"] = full_clean(user_inf["activities"])

    if "interests" in user_inf:
        info["interests"] = [ full_clean(m) for m in user_inf["interests"].split(',') if full_clean(m) != '' ]

    if "music" in user_inf:
        info["music"] = [ full_clean(m) for m in user_inf["music"].split(',') if full_clean(m) != '' ]

    if "movies" in user_inf:
        info["movies"] = [ full_clean(m) for m in user_inf["movies"].split(',') if full_clean(m) != '' ]

    if "tv" in user_inf:
        info["tv"] = [ full_clean(m) for m in user_inf["tv"].split(',') if full_clean(m) != '' ]

    if "books" in user_inf:
        info["books"] = [ full_clean(m) for m in user_inf["books"].split(',') if full_clean(m) != '' ]

    if "games" in user_inf:
        info["games"] = [ full_clean(m) for m in user_inf["games"].split(',') if full_clean(m) != '' ]

    if groups_intersections:
        info['groups_of_interest']=[]
        for group_name in groups_intersections:
            if user_inf['id'] in groups_intersections[group_name]: info['groups_of_interest']+=[group_name]

    return info


def loadAllCommunityMembers(community_id,max_users=None,user_ids = [], load_groups_intersections = True):
    if os.path.isfile("vkdata/%s_users.pkl" % community_id):
        return pickle.load(open("vkdata/%s_users.pkl" % community_id,"rb"))
    else:
        if len(user_ids) == 0:
            user_ids = getCommunityMembers(community_id)
            tqdm.tqdm.write("{} ids loaded for {}".format(user_ids.__len__(),community_id))
            if(max_users):
                user_ids = get_shuffled(user_ids,max_users)

        if load_groups_intersections:
            groups_intersections = { group_name:set(getMembersIntersection(user_ids,group_name)) for group_name in groups_of_interest.keys() }
        else:
            groups_intersections = None

        tqdm.tqdm.write ("%s groups_intersection loaded" % community_id)

        tqdm.tqdm.write("starting to load info for {} users".format(user_ids.__len__()))
        users_infos = getUsersInfo(user_ids)
        tqdm.tqdm.write ("%s users_infos loaded, count %s, ids count %s" % (community_id,len(users_infos),len(user_ids)))

        users_infos = [ transformUserInfo(u, groups_intersections) for u in users_infos ]
        tqdm.tqdm.write  ("%s users_infos transformd" % community_id)
        pickle.dump(users_infos,open("vkdata/%s_users.pkl" % community_id,"wb"))
        return users_infos

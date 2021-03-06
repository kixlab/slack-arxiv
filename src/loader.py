from history_script import getHistory, doTestAuth, getUserMap
import argparse
import os
import glob
import json
from slacker import Slacker
import logging
import requests
import time
from elasticsearch import Elasticsearch, helpers
from cmreslogging.handlers import CMRESHandler

handler = CMRESHandler(hosts=[{'host': 'elasticsearch', 'port': 9200 }],
                       index_name_frequency=CMRESHandler.IndexNameFrequency.MONTHLY,
                       auth_type=CMRESHandler.AuthType.NO_AUTH,
                       es_index_name="logs-collector")
FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)

log = logging.getLogger("slack-arxiv")
log.addHandler(handler)

def format_message(message, user_id_name_map, channel_name):
    try:
        message['username'] = user_id_name_map[message['user']] \
            if 'user' in message else 'slack'
    except KeyError as e:
        log.error(e)
    message['channel_name'] = channel_name
    message['ts'] = int(float(message['ts'])) * 1000
    return message


def load_exported(export_path, usermap):
    export_path = os.path.join('/dump_data', export_path)
    messages = []

    channels = os.listdir(export_path)
    for channel in channels:
        log.info("EXPORT: handling #{}".format(channel))
        message_files = glob.glob(
            os.path.join(export_path, channel, '*.json'))
        for file in message_files:
            with open(file) as f:
                daily_messages = json.load(f)
                formatted_messages = [format_message(m, usermap, channel) for m
                                      in daily_messages]
                messages.extend(formatted_messages)

    log.info("EXPORT: total {} messages collected"
                 .format(len(messages)))
    return messages


def load_history(slack, usermap, latest_timestamp=0):
    log.info("HISTORY: loading after {}"
                 .format(latest_timestamp))
    channels = slack.channels.list().body['channels']
    messages = []
    for channel in channels:
        log.info("HISTORY: handling #{}".format(channel['name']))
        ch_messages = getHistory(slack.channels, channel['id'])
        ch_messages_formatted = [
            format_message(m, usermap, channel['name'])
            for m in ch_messages
            if int(float(m['ts'])) > latest_timestamp
        ]
        messages.extend(ch_messages_formatted)
    log.info("HISTORY: total {} messages collected"
                 .format(len(messages)))
    return messages


def index_messages(es, messages, index_name):
    log.info("{} messages to {}".format(len(messages), es_host))
    actions = ({
        '_index': index_name,
        '_type': "message",
        '_source': message,
    } for message in messages)
    action_results = helpers.bulk(es, actions)
    log.info("Indexing finished. {}"
                 .format(json.dumps(action_results, indent=4)))
    return


def get_latest_timestamp(es):
    results = es.search(index='message-arxiv', body={
        "query": {
            "match_all": {}
        },
        "size": 1,
        "sort": [
            {
                "ts": {
                    "order": "desc"
                }
            }
        ]
    })
    if len(results) == 0:
        return 0
    return int(results['hits']['hits'][0]['_source']['ts'] / 1000)


def check_index(index_name=''):
    index_uri = os.path.join(os.environ.get('ES_HOST'), index_name)
    mapping = {
        "mappings": {
            "message": {
                "properties": {
                    "ts": {
                        "type": "date"
                    }
                }
            }
        }
    }
    resp = requests.get(index_uri).json()
    if 'error' in resp:
        log.info("Creating {} index".format(index_name))
        create_index_result = requests.put(index_uri, json=mapping).json()
        log.info("Result {}".format(json.dumps(create_index_result, indent=4)))
    else:
        log.info("Index {} exists already".format(index_name))
        log.info(json.dumps(resp, indent=4))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    token = os.environ.get('SLACK_LEGACY_TOKEN')
    parser.add_argument(
        '--export_dir',
        help="The path of unzipped export file from slack")
    parser.add_argument(
        '--dump_history',
        action='store_true',
        default=False,
        help="Fetch latest messages using history api")
    parser.add_argument(
        '--keep_crawling',
        action='store_true',
        default=False,
        help="Fetch latest messages using history api")
    args = parser.parse_args()
    log.info(args)

    slack = Slacker(token)
    testAuth = doTestAuth(slack)
    userIdNameMap = getUserMap(slack)
    index_name = 'message-arxiv'
    es_host = os.environ.get('ES_HOST')
    es = Elasticsearch(hosts=[es_host])
    check_index(index_name)

    if args.export_dir:
        log.info("Getting dumped messages from files")
        messages_exported = load_exported(args.export_dir, userIdNameMap)
        index_messages(es, messages_exported, index_name)

    if args.dump_history:
        log.info("Getting recent messages from history api")
        while True:
            try:
                latest_ts_from_es = get_latest_timestamp(es)
                messages_history = load_history(slack, userIdNameMap, latest_ts_from_es)
                index_messages(es, messages_history, index_name)
            except requests.exceptions.ConnectionError as e:
                log.warning(e)
                log.warning("Retrying after 16 hours")
                time.sleep(16 * 60 * 60)
                continue
            if not args.keep_crawling:
                break
            else:
                log.info("Updated successfully")
                time.sleep(2 * 60 * 60)

from history_script import getHistory, doTestAuth, getUserMap

import argparse
import os
import glob
import json
from slacker import Slacker
import logging
import requests
from elasticsearch import Elasticsearch, helpers

logging.basicConfig(level=logging.INFO)


def format_message(message, user_id_name_map, channel_name):
    try:
        message['username'] = user_id_name_map[message['user']] \
            if 'user' in message else 'slack'
    except KeyError as e:
        print(e)
    message['channel_name'] = channel_name
    message['ts'] = int(float(message['ts'])) * 1000
    return message


def load_exported(export_path, usermap):
    export_path = os.path.join('/dump_data', export_path)
    messages = []

    channels = os.listdir(export_path)
    for channel in channels:
        logging.info("EXPORT: handling #{}".format(channel))
        message_files = glob.glob(
            os.path.join(export_path, channel, '*.json'))
        for file in message_files:
            with open(file) as f:
                daily_messages = json.load(f)
                formatted_messages = [format_message(m, usermap, channel) for m
                                      in daily_messages]
                messages.extend(formatted_messages)

    logging.info("EXPORT: total {} messages collected"
                 .format(len(messages)))
    return messages


def load_history(slack, usermap, latest_timestamp=0):
    logging.info("HISTORY: loading after {}"
                 .format(latest_timestamp))
    channels = slack.channels.list().body['channels']
    messages = []
    for channel in channels:
        logging.info("HISTORY: handling #{}".format(channel['name']))
        ch_messages = getHistory(slack.channels, channel['id'])
        ch_messages_formatted = [
            format_message(m, usermap, channel['name'])
            for m in ch_messages
            if float(m['ts']) > latest_timestamp
        ]
        messages.extend(ch_messages_formatted)
    logging.info("HISTORY: total {} messages collected"
                 .format(len(messages)))
    return messages


def index_messages(es, messages, index_name):
    logging.info("{} messages to {}".format(len(messages), es_host))
    actions = ({
        '_index': index_name,
        '_type': "message",
        '_source': message,
    } for message in messages)
    action_results = helpers.bulk(es, actions)
    logging.info("Indexing finished. {}"
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
        logging.info("Creating {} index".format(index_name))
        create_index_result = requests.put(index_uri, json=mapping).json()
        logging.info("Result {}".format(json.dumps(create_index_result, indent=4)))
    else:
        logging.info("Index {} exists already".format(index_name))
        logging.info(json.dumps(resp, indent=4))


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
    args = parser.parse_args()
    print(args)

    slack = Slacker(token)
    testAuth = doTestAuth(slack)
    userIdNameMap = getUserMap(slack)
    index_name = 'message-arxiv'
    es_host = os.environ.get('ES_HOST')
    es = Elasticsearch(hosts=[es_host])
    check_index(index_name)

    if args.export_dir:
        logging.info("Getting dumped messages from files")
        messages_exported = load_exported(args.export_dir, userIdNameMap)
        index_messages(es, messages_exported, index_name)

    if args.dump_history:
        logging.info("Getting recent messages from history api")
        latest_ts_from_es = get_latest_timestamp(es)
        messages_history = load_history(slack, userIdNameMap, latest_ts_from_es)
        index_messages(es, messages_history, index_name)

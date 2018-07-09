# Slack-arxiv

Where Kixlab's slack messages are archived. Messages are indexed in Elasticsearch, and only lab members can search them using Kibana served by [OAuth proxy server](https://github.com/bitly/oauth2_proxy).

How to run
---
1. Create GitHub OAuth app [link](https://github.com/settings/developers)
2. Create Slack legacy token [here](https://api.slack.com/custom-integrations/legacy-tokens)
3. Create `.env` file like [.env.example](https://github.com/kixlab/slack-arxiv/blob/master/.env.example)
```commandline
docker-compose up
```
3. Now proxied Kibana is up at port 4180.

How to fetch latest history, and keep crawling every two hour
---
```commandline
docker-compose run collector python loader.py --dump_history --keep_crawling
```

How to import exported files
---
1. Dump all the message [here](https://get.slack.help/hc/en-us/articles/201658943-Export-data-and-message-history)
2. Copy dumped data inside `dump_data` folder
3. Pass the **name of directory** (not path) as argument in the command below
```commandline
docker-compose run collector python loader.py --export_dir NAME_OF_DIRECTORY
```

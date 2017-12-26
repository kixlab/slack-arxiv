# Slack-arxiv

Where Kixlab's slack messages are archived. Messages are indexed in Elasticsearch, and lab members can search it using Kibana under [OAuth proxy server](https://github.com/bitly/oauth2_proxy).

How to run
---
1. Create GitHub OAuth app [link](https://github.com/settings/developers)
2. Fill `.env` file
```commandline
docker-compose up
```
3. Now proxied(?) Kibana is up at port 4601.

How to fetch latest history, and keep crawling every two hour
---
```commandline
docker-compose run collector python loader.py --dump_history --keep-crawling
```

How to import exported files
---
1. Copy dumped data inside `dump_data` folder
2. Pass the **name of directory** (not path) as argument in the command below
```commandline
docker-compose run collector python loader.py --export_dir NAME_OF_DIRECTORY
```

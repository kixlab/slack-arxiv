How to run
```commandline
docker-compose up
```

How to fetch latest history
```commandline
docker-compose run dump python loader.py --dump_history
```

How to import exported files
1. Copy dumped data inside `dump_data` folder
2. Pass the **name of directory** (not path) as argument in the command below
```commandline
docker-compose run dump python loader.py --export_dir NAME_OF_DIRECTORY
```

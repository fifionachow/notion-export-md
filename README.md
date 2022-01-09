# Using Notion API to export Notion Pages for Hugo blog

## Setup
```
>>> cd notion-export-md
>>> pip install -e requirements.txt
>>> export NOTION_API_TOKEN=<INSERT_API_KEY>
```

## Use

- Update `config.py` with local directory and targeted Notion database/page
- To export and publish (commit and push to Github) Notion pages as Hugo articles:
```
>>> python notion2md.py --config ./config.py --publish
```

Note: To export and not publish, remove `--publish`

## TODO
- To export and publish all Notion pages where `Status='Ready to Publish'`
- To update Notion pages with `Status='Published'`
- Execute `deploy.sh` script

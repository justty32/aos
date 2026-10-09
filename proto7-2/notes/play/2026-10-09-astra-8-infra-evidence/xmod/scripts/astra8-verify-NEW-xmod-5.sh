PYTHONDONTWRITEBYTECODE=1 python3 -B wf/tools/tabledb.py \
  proto7-2/notes/blueprint-errors-items.json find pack=author
PYTHONDONTWRITEBYTECODE=1 python3 -B wf/tools/tabledb.py \
  proto7-2/notes/blueprint-errors-items.json find pack=mail
rg -n 'CODES =|return 3|up（設計中）' \
  proto7-2/packs/author/aos7_author.py \
  proto7-2/modules/mail/aos7_mail_cli.py \
  proto7-2/notes/blueprint-errors-items.json

T=$(mktemp -d /tmp/astra8-xmod-entry-XXXX)
P="$PWD/proto7-2"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$T/home" "$T/slot"
printf '{' > "$T/slot/birth.json"
(
  cd "$T"
  export HOME="$T/home"
  python3 -B "$P/bin/aos7-ctl" --no-such-option
  printf 'ctl bad rc=%s\n' "$?"
  python3 -B "$P/bin/aos7-ctl" task "$T/slot" kill
  printf 'ctl unknown rc=%s\n' "$?"
  python3 -B "$P/packs/adapt/bin/aos7-adapt" --no-such-option
  printf 'adapt bad rc=%s\n' "$?"
  python3 -B "$P/packs/usage/bin/aos7-usage" --help
  printf 'usage help rc=%s\n' "$?"
)
rm -rf "$T"

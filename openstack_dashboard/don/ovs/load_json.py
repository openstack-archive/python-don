import pprint
import sys

from common import load_json

if len(sys.argv) != 2:
    print ('Usage: ' + sys.argv[0] + ' <json file to display>')
    exit(1)

info = load_json(sys.argv[1])
pprint.pprint(info)

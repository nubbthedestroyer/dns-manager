#!/usr/bin/python
import json

limit = 26
# domains = 20

# for index, domain in izip(xrange(limit), domains):
#     print(item)

domains = {}
index = 0

while True:
    if index == limit:
        break
    newdom = {
        "abc" + str(index): {
            'domain': "abc" + str(index) + '.com',
            'alb': '1'
        }
    }
    domains.update(newdom)
    domains.update({"abc23-2": {
        "domain": "abc23-2.com",
        "alb": "2"
    },
    "abc20-2": {
        "domain": "abc20-2.com",
        "alb": ""
    }})
    index = index + 1
    # print index

# print(json.dumps(domains, indent=4))
with open('data.json', 'w') as f:
    f.write(json.dumps(domains, indent=4))



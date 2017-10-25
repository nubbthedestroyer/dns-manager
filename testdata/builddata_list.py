#!/usr/bin/python
import json

limit = 100
# domains = 20

# for index, domain in izip(xrange(limit), domains):
#     print(item)

domains = []
index = 0
alb_iter = 0
alb_num = 1

doms_per_alb = 50

while True:
    if index == limit:
        break
    newdom = {
        'domain': "hwgdskalquwdtcsaasdfg" + str(index) + '.com',
        'alb': alb_num
    }
    domains.append(newdom)
    index = index + 1
    alb_iter = alb_iter + 1
    # try:
    if alb_iter == doms_per_alb:
        alb_num = alb_num + 1
        alb_iter = 0

    # except ZeroDivisionError:
    #     pass
    # print index

# domains.append({
#         "domain": "awerfghbvcxsdfgh.com",
#         "alb": "2456789"
#     })
# domains.append({
#     "domain": "asdfghgfdsrtgyh.com",
#     "alb": ""
# })

# print(json.dumps(domains, indent=4))
with open('data.json', 'w') as f:
    f.write(json.dumps(domains, indent=4))



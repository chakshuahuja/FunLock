import json
import matplotlib
import pylab
import sys
import matplotlib.pyplot as plt

train = json.loads(open(sys.argv[1]).read())
test = json.loads(open(sys.argv[2]).read())
key_maps = {}
i = 0
for k, v in train.items():
    if k in key_maps.keys():
        continue
    key_maps[k] = i
    i = i + 1

for k, v in test.items():
    if k in key_maps.keys():
        continue
    key_maps[k] = i
    i = i + 1
print 'KEYMAPS:', key_maps

train_points = []
test_points = []
train_avg, test_avg = {}, {}
for k,v in train.items(): 
    if train != {}:
        avg = sum(v)/len(v)
        train_avg[k] = avg
        train_points.append((key_maps[k], avg))
print train_avg
for k,v in test.items(): 
    if test != {}:
        avg = sum(v)/len(v)
        test_avg[k] = avg
        test_points.append((key_maps[k], avg))
print test_avg
result = {}
for k in train.keys():
    if (test_avg[k] <= (train_avg[k] + 20)) and (test_avg[k] >= (train_avg[k]-20)):
        result[k] = True
    else:
        result[k] = False

print sum(result.values())/float(len(result.values())) 
x1,y1 = zip(*train_points)
x2,y2 = zip(*test_points)

C = x1, y1
S =  x2, y2

plt.scatter(x1, y1, color="blue", linewidth=1.0, linestyle="-")

plt.scatter(x2, y2, color="green", linewidth=1.0, linestyle="-")

matplotlib.pyplot.show()

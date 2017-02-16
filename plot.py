import json
import matplotlib
import pylab
import sys

d = json.loads(open(sys.argv[1]).read())

values = d.values()
print values
points = []
for i,v in enumerate(values):
    # Use this if you are interested in whole range of force applied on every key
    if len(v) > 0:
        for value in v:
             points.append((i, value))
    # Use this if you are only interested in average force on every key
    if len(v) > 0:
        avg = sum(v)/len(v)
        points.append((i, avg))
x,y = zip(*points)

matplotlib.pyplot.scatter(x,y)
matplotlib.pyplot.show()

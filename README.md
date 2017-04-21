# Talavera

![talavera tiles](http://www.lafuente.com/images/alternate/til217a.jpg =200px)

A python tiling utility for GBDX Vector Services. 

Talavera can be used in a number of ways: as a lambda function, a cli, or 
programmably in python. The goal is provide an way to predictably generate and view vector tiles 
from queries to Vector Services. 

## Installation

```python
pip install talavera
```

## Usage

### Lamda 

As a lambda function Talavera can be used as fully functioning tilecache. It connects accepts a query param and z/x/y coords, 
fetches data and writes to an s3 repo.

You can prepare a .zip file for uploading to Lambda via:

```
./publish.sh s3-bucket zip-name
```

This will create a zip file with all the required deps and code needed to create a lambda fn.

### Seed

Cache seeding is primarily used for dev purposes. Its beneficial to selectively cache tiles for testing and viz purposes, and to not
needlessly burden the production vector services servers...

Here we show how we can seed tiles for a given AOI and zoom level range. This will seed the cache for all IDAHO footprints in the AOI:

```
query = 'item_type:DigitalGlobeProduct AND item_type:IDAHOImage AND (item_type:WV03_VNIR or item_type:WV02)'
bbox = [151.22397593516195, -33.885183724768375, 151.27817676849645, -33.85025891132142] 

seed(bbox, query, zooms=range(3,16), force=True)
```


### Visualization

In order to quickly visualize tiles there's method in Talavera that renders a mapbox-gl map of cached tiles:

```
tilemap('ingest_source:OSM AND item_type:Building', zoom=14, lon=-104.993720, lat=39.748048)
```


## TODO

* lots
* Data pagination so we dont hit query count limit in single tiles
* intelligent cache expiration
* more composible map viz class (configurable layer defs, styles, etc)
* low zoom level aggregations


## BEWARE OF PROTOTYPES

This project was developed as part of the Q2 2017 Platform Hackathon, and is a PROTOTYPE, 
not completely functional, and still a ways from being production ready.

In other words: "DONT LET CHELM USE THIS IN PRODUCTION... YET"

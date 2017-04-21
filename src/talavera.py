from __future__ import print_function
from hashlib import sha256
import json
import mapbox_vector_tile as mvt
import mercantile
import requests   
from shapely.geometry import shape, box
import shapely.ops
from functools import partial
import pyproj

from boto.s3.connection import S3Connection
import tempfile

def respond(res):
    return res
    #body = {
    #    'location': res,
    #}
    #return {
    #    "statusCode": code,
    #    "headers": {
    #        "Content-Type": "application/json",
    #       "Content-Length": len(str(body)),
    #       "Location": res
    #   },
    #   "location": json.dumps(body)
    #}

def handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    if 'queryStringParameters' in event:
        params = event['queryStringParameters']
    else:
        params = None

    if params is None:
        return respond('Need params', 500)
    elif 'token' not in params: 
        return respond('Need token', 500)
    elif 'query' not in params:
        return respond('Need query', 500)
    elif 'z' not in params or 'y' not in params or 'x' not in params:
        return respond('Need zxy coords', 500)

    
    fmt = 'json'
    if 'format' in params:
        fmt = params['format']
    
    s3 = S3Connection()
    bucket = s3.get_bucket('idaho-vrt-chelm')

    token = params['token']
    query = params['query']
    z = int(params['z'])
    x = int(params['x'])
    y = int(params['y'])

    if 'server' not in params:
        server = 'vector.geobigdata.io'
    else:
        server = params['server']
    print('HASH', server, query, sha256(str(query).encode('utf-8')).hexdigest())
    cache_key = "/".join(["vtiles", str(z), str(x), str(y), sha256(str(query).encode('utf-8')).hexdigest()]) + "." + fmt
    
    exists = bucket.get_key(cache_key, headers=None, version_id=None, response_headers=None, validate=True)
    if exists is not None and 'force' not in params:
        print('Found Tile in Cache', cache_key)
        return respond('https://s3.amazonaws.com/idaho-vrt-chelm/{}'.format(cache_key))
    else:
        print('Creating new tile')
        bbox = list(mercantile.bounds(x,y,z))
        bounds = {"left": bbox[0], "lower": bbox[1], "right": bbox[2], "upper": bbox[3]}
        
        headers = { 'Authorization': 'Bearer {}'.format(token) }
        resp = requests.get("https://{}/insight-vector/api/vectors/query/items".format(server), params=dict(count=1000, q=query, **bounds), headers=headers)

        try: 
            features = json.loads(resp.content)
            print(len(features))
        except Exception as err:
            return respond(err, resp.status_code)

        temp = tempfile.NamedTemporaryFile(suffix=fmt)
        if fmt == 'json':
            geojson = {'type': 'FeatureCollection', 'features': features}
            with open(temp.name, 'w') as f:
                json.dump(geojson, f)
        elif fmt == 'pbf':
            # convert to vector tile
            tile = mvt.encode({
              "name": 'gbdx',
              "features": [encode_tile(bbox, f) for f in features]
            })
            with open(temp.name, 'wb') as f:
                f.write(tile)

        print('Saving tile to cache') 
        key = bucket.new_key(cache_key)
        key.set_contents_from_filename(temp.name)
        temp.delete
        return respond('https://s3.amazonaws.com/idaho-vrt-chelm/{}'.format(cache_key))
 
def project(shp, in_proj='4326', out_proj='3857'):
    # Suppose geometry is an instance of shapely.geometry.Geometry
    tfm = partial(pyproj.transform, 
              pyproj.Proj(init="epsg:{}".format(in_proj)), 
              pyproj.Proj(init="epsg:{}".format(out_proj)))
    return shapely.ops.transform(tfm, shp) 

def encode_tile(bbox, feature):
    MVT_EXTENT = 4096
    box_shp = project(box(*bbox))
    shp = project(shape(feature["geometry"]).buffer(0))

    (x0, y0, x_max, y_max) = box_shp.bounds
    x_span = x_max - x0
    y_span = y_max - y0
    def xform(xs,ys):
        xs = tuple([int((x - x0) * MVT_EXTENT / x_span) for x in xs])
        ys = tuple([int((y - y0) * MVT_EXTENT / y_span) for y in ys])
        return (xs, ys)

    geom = shapely.ops.transform(xform, shp)
    return {
      "geometry": geom.wkb,
      "properties": feature['properties']
    }
 

if __name__ == "__main__":
    token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2RpZ2l0YWxnbG9iZS1wbGF0Zm9ybS5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8Z2JkeHwyMTY2OCIsImF1ZCI6InZoYU5FSnltTDRtMVVDbzRUcVhtdUt0a245SkNZRGtUIiwiZXhwIjoxNDkzMjI5Mjk3LCJpYXQiOjE0OTI2MjQ0OTcsImF6cCI6InZoYU5FSnltTDRtMVVDbzRUcVhtdUt0a245SkNZRGtUIn0.xBgnhoNcSFJckhZWD8bb2U1raHtOoJpeG6xtRwrk0Hg'
    event = {
      'queryStringParameters': {
        'token': token,
        'server': 'vector.geobigdata.io',
        #'query': 'ingest_source:PSMA-GeoScape AND item_type:Building',
        #'query': 'item_type:DigitalGlobeProduct AND item_type:IDAHOImage AND (item_type:WV03_VNIR or item_type:WV02)',
        'query': 'ingest_source:OSM AND item_type:Building',
        #'z': "3",
        #'x': "7",
        #'y': "4",
        'x': 106, 
        'y': 194,
        'z': 9,
        'format': 'pbf',
        'force': True
      }
    }
    handler(event, {})

    #query = ["ingest_source:PSMA-GeoScape"]
    #bounds = {"left": -180, "lower": -90, "upper": 90, "right": 180}

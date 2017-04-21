from __future__ import print_function
import boto3
import json

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

from string import Template
from hashlib import sha256

from gbdxtools import Interface
gbdx = Interface()

_session = boto3.Session(profile_name='dg')
_lambda = _session.client("lambda")


def seed(bbox, query, zooms=range(5,15), fmt="pbf", force=False, server='vector.geobigdata.io'):
    params = bbox + [zooms]
    for t in mercantile.tiles(*params):
        data = {
            "queryStringParameters": {
                "token": gbdx.gbdx_connection.access_token,
                "query": query,
                "server": server,
                "z": t.z,
                "x": t.x,
                "y": t.y,
                "format": fmt,
                "force": force
            }
        }
        response = _lambda.invoke(
            FunctionName='talavera',
            InvocationType='RequestResponse',
            Payload=json.dumps(data)
        )
        print(response['StatusCode'], t.z, t.x, t.y)



def tilemap(query, zoom=15, lon=151.25023462361236, lat=-33.864604097323536, extrude=None):
    from IPython.display import Javascript, HTML, display

    if extrude is None:
        extrude = ''
    qhash = sha256(str(query).encode('utf-8')).hexdigest()

    display(HTML('''
        <div id="map"/>
        <style>body{margin:0;padding:0;}#map{position:relative;top:0;bottom:0;width:100%;height:400px;}</style>
    '''))

    js = Template("""
        require.config({
          paths: {
              mapboxgl: 'https://api.tiles.mapbox.com/mapbox-gl-js/v0.34.0/mapbox-gl',
          }
        });

        require(['mapboxgl'], function(mapboxgl){
            mapboxgl.accessToken = "pk.eyJ1IjoicHJhbXVrdGEiLCJhIjoiY2l3ZjhuYTJiMGFieTJ0bzV5ZHFvYmlydiJ9.Y16spXi1Gxj7-mrjl_YlGQ"
            window.map = new mapboxgl.Map({
                container: 'map', 
                style: 'mapbox://styles/mapbox/dark-v8', 
                center: [$lon, $lat], 
                zoom: $zoom
            });
            var map = window.map;
            map.once('style.load', function(e) {
                function addLayer(mapid) {
                    try {
                        mapid.addSource('tiles', 
                        {
                            type: "vector",
                            tiles: ["https://s3.amazonaws.com/idaho-vrt-chelm/vtiles/{z}/{x}/{y}/$qhash.pbf"]
                        });
                        
                        var extrude = "$extrude";
                        if ( extrude === "") {
                            var layer =  {
                                "id": "gbdx",
                                "type": "fill",
                                "source": "tiles",
                                "source-layer": "gbdx",
                                "paint": {
                                   "fill-color": '#0088CC',
                                   "fill-opacity": .25
                                }
                            };
                        } else {
                            var layer =  {
                                "id": "gbdx",
                                "type": "fill-extrusion",
                                "source": "tiles",
                                "source-layer": "gbdx",
                                "paint": {
                                  'fill-extrusion-height': {
                                          property: extrude,
                                          type: 'exponential',
                                          stops: [
                                            [1, 2],
                                            [50, 4],
                                            [500, 10]
                                          ]
                                        },
                                  'fill-extrusion-opacity': 0.6,
                                  'fill-extrusion-base': 0,
                                  "fill-extrusion-color": '#5588de',
                                }
                            };
                        }
                        mapid.addLayer(layer);
                        
                    } catch (err) {
                        console.log(err);
                    }
                }

                addLayer(map)
            });

        });
    """).substitute({"qhash": qhash, "lat": lat, "lon": lon, "zoom": zoom, "extrude": extrude})
    display(Javascript(js))

def respond(res):
    return res

def lambda_handler(event, context):
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
    print('HASH', query, sha256(str(query).encode('utf-8')).hexdigest())
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
        resp = requests.get("https://{}/insight-vector/api/vectors/query/items".format(server), params=dict(count=500, q=" ".join(query), **bounds), headers=headers)

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
        'server': 'devvector.geobigdata.io',
        #'query': 'ingest_source:PSMA-GeoScape',
        'query': 'item_type:DigitalGlobeProduct AND item_type:IDAHOImage AND (item_type:WV03_VNIR or item_type:WV02)',
        'z': "5",
        'x': "5",
        'y': "12",
        'format': 'pbf',
        'force': True
      }
    }
    handler(event, {})

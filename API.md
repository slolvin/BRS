# API Documentation: BRS
<h2>Description</h2>
This is an API to work with BRS (BarRateStars)
-----
<h2>General information</h2>
<ul>
    <li><b>API Base URL:</b> http://localhost:8000</li>
    <li><b>API Version:</b> 0.1</li>
    <li><b>Contact Email:</b> shleppel@yandex.ru</li>
    <li><b>Authentication Method:</b> </li>
</ul>

-----
<h2>Authentication</h2>
<p>curl -u "<b>mail</b>:<b>password</b>" GET http://<b>addres</b>:8000 -H "Accept: application/json"</p>
<p>Token based</p>
<h3>Authentication Example</h3>

-----
<h2>Error Codes</h2>
<table>
  <tr>
    <th>Code</th>
    <th>Message</th>
    <th>Description</th>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>

-----
<h2>Resources/Endpoints</h2>
<h3>Bar</h3>

[//]: # (Get all bars list)
<h5>Method: GET</h5>
<h4>URL</h4> /api/v1.0/bars/
<h4>Description</h4>
Get all bars list
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">City</td>
            <td align="center">String</td>
            <td align="center">False</td>
            <td align="left">Location for search</td>
        </tr>
        <tr>
            <td align="center">Range</td>
            <td align="center">Int</td>
            <td align="center">False</td>
            <td align="left">Range for search (meters)</td>
        </tr>
        <tr bgcolor="yellow">
            <td align="center">Page</td>
            <td align="center">Int</td>
            <td align="center">False</td>
            <td align="center">Pages from list (5 on page)</td>
        </tr>
        <tr>
            <td align="center"></td>
            <td align="center"></td>
            <td align="center"></td>
            <td align="center"></td>
        </tr>
    </table>
<h4>Example Request:</h4>
<h4>Example Response:</h4>
{
"bars":[
  {"address":"\u0443\u043b. \u041a\u0443\u0439\u0431\u044b\u0448\u0435\u0432\u0430, 78, \u0421\u0430\u043c\u0430\u0440\u0430, \u0421\u0430\u043c\u0430\u0440\u0441\u043a\u0430\u044f \u043e\u0431\u043b., 443099","city":"\u0421\u0430\u043c\u0430\u0440\u0430","name":"KeKeRS"},
  {"address":"st.Main 10","city":"\u041c\u043e\u0441\u043a\u0432\u0430","name":"Not the best bar"},
  {"address":"st.Main 12","city":"\u041c\u043e\u0441\u043a\u0432\u0430","name":"Best bar ever"}]
    "count":5,"next":"/api/v1.0/bars/?page=2","prev":null}]
}

[//]: # (Get single bar info)
<h5>Method: GET</h5>
<h4>URL</h4> /api/v1.0/bars/bar_id
<h4>Description</h4>
Get single bar info
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">ID</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="left">Bar ID</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    GET /api/v1.0/bars/8/
    curl -u "sl@sl:sl" GET http://localhost:8000/api/v1.0/bars/8 -H "Accept: application/json"
<h4>Example Response:</h4>
    { id:, name: admin_id;,city:, address:, drinks[], rate}
curl: (6) Could not resolve host: GET
{"address":"\u0443\u043b. \u041a\u0443\u0439\u0431\u044b\u0448\u0435\u0432\u0430, 81, \u0421\u0430\u043c\u0430\u0440\u0430, \u0421\u0430\u043c\u0430\u0440\u0441\u043a\u0430\u044f \u043e\u0431\u043b., 443099","city":"\u0421\u0430\u043c\u0430\u0440\u0430","name":"BARSUK"}

[//]: # (Create new bar)
<h5>Method: POST</h5>
<h4>URL</h4> /api/v1.0/bars/
<h4>Description</h4>
Add new bar into list
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">name</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="left">Bar name</td>
        </tr>
        <tr>
            <td align="center">address</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="left">Bar address</td>
        </tr>
        <tr>
            <td align="center">city</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="left">Location city</td>
        </tr>
        <tr>
            <td align="center">admin_id</td>
            <td align="center">Int</td>
            <td align="center">True</td>
            <td align="left">For test version 3 or 4</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    curl -u "sl@sl:sl" POST http://localhost:8000/api/v1.0/bars/ -H "Content-Type: application/json" -d '{"name":"Siske","address":"SisStr","admin_id":"3","city":"Samara"}'
<h4>Example Response:</h4>
    {"address":"SisStr","city":"Samara","name":"Siske"}

[//]: # (Update bar)
<h3>User</h3>

[//]: # (Get all users list)
<h5>Method: GET</h5>
<h4>URL</h4> /api/v1.0/users/
<h4>Description</h4> Get all users
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr bgcolor="yellow">
            <td align="center">Page</td>
            <td align="center">Int</td>
            <td align="center">False</td>
            <td align="center">Users per request (5 by default)</td>
        </tr>
        <tr>
            <td align="center">role</td>
            <td align="center">String (Select?)</td>
            <td align="center">False</td>
            <td align="center">Filter users by role</td>
        </tr>
    </table>
<h4>Response Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">id</td>
            <td align="center">Int</td>
            <td align="center">User ID</td>
        </tr>
        <tr>
            <td align="center">username</td>
            <td align="center">String</td>
            <td align="center">Username</td>
        </tr>
        <tr>
            <td align="center">email</td>
            <td align="center">String</td>
            <td align="center">User email</td>
        </tr>
        <tr>
            <td align="center">type</td>
            <td align="center">String</td>
            <td align="center">User role</td>
        </tr>
        <tr>
            <td align="center">location</td>
            <td align="center">String</td>
            <td align="center">City</td>
        </tr>
        <tr>
            <td align="center">aboutMe</td>
            <td align="center">String</td>
            <td align="center">Bio</td>
        </tr>
        <tr>
            <td align="center">memberSinse</td>
            <td align="center">TimeStamp</td>
            <td align="center">Date of registration</td>
        </tr>
        <tr>
            <td align="center">lastSeen</td>
            <td align="center">TimeStamp</td>
            <td align="center">Date of last LogIn</td>
        </tr>
        <tr>
            <td align="center">avatarHash</td>
            <td align="center">String</td>
            <td align="center">Link to users avatar</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    GET /api/v1.0/users/
    curl -u "sl@sl:sl" GET http://localhost:8000/api/v1.0/users/ -H "Accept: application/json" -d '{"role":"admin""}'
<h4>Example Response:</h4>
    {"count":10,"users":[
                            {"id":8,"username":"sl"","email":"sl@sl","type":"admin","location":"Samara","about_me":"New guy","member_since":"2026.01.06","last_seen":"2026.01.06","avatar_hash":"avatar_url"}],
    "next":"/api/v1.0/users/?page=2","prev":null}

[//]: # (Get single user info)
<h5>Method: GET</h5>
<h4>URL</h4> /api/v1.0/users/7
<h4>Description</h4> Get info about single user
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">id</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="left">User ID</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    GET /api/v1.0/users/7/
    curl -u "sl@sl:sl" GET http://localhost:8000/api/v1.0/users/7 -H "Accept: application/json"
<h4>Example Response:</h4>

[//]: # (Create new user)
<h5>Method: POST</h5>
<h4>URL</h4> /api/v1.0/users/
<h4>Description</h4> Create new user
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">username</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="center">User name</td>
        </tr>
        <tr>
            <td align="center">email</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="center">User email</td>
        </tr>
        <tr>
            <td align="center">password</td>
            <td align="center">String (secure)</td>
            <td align="center">True</td>
            <td align="center">User password</td>
        </tr>
        <tr>
            <td align="center">location</td>
            <td align="center">Sting</td>
            <td align="center">False</td>
            <td align="center">City of user</td>
        </tr>
        <tr>
            <td align="center">bio</td>
            <td align="center">String</td>
            <td align="center">False</td>
            <td align="center">User description</td>
        </tr>
        <tr>
            <td align="center">avatar</td>
            <td align="center">String</td>
            <td align="center">False</td>
            <td align="center">URL for user avatar</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    POST /api/v1.0/drinks/
    curl -u "sl@sl:sl" POST http://localhost:8000/api/v1.0/users/ -H "Accept: application/json" -d '{"username":"Joe","email":"Doe@Doe","password":"*****","location":"Samara","bio":"Big peppa","avatar":"avatarURL"}'
<h4>Example Response:</h4>
    {"username":"Joe","email":"Doe@Doe","password":"*****","location":"Samara","bio":"Big peppa","avatar":"avatarURL"}

[//]: # (Update user)
<h3>Drink</h3>

[//]: # (Get all drinks list)
<h5>Method: GET</h5>
<h4>URL</h4>
/api/v1.0/drinks/?page=2
<h4>Description</h4>
Get all exists drinks
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr bgcolor="yellow">
            <td align="center">Page</td>
            <td align="center">Int</td>
            <td align="center">False</td>
            <td align="center">Drinks per request (5 by default)</td>
        </tr>
        <tr>
            <td align="center">Type</td>
            <td align="center">String (Select?)</td>
            <td align="center">False</td>
            <td align="center">Filter drinks by type</td>
        </tr>
    </table>
<h4>Example Request:</h4>
curl -u "sl@sl:sl" GET http://localhost:8000/api/v1.0/drinks/?page=2 -H "Accept: application/json"
<h4>Example Response:</h4>
{"count":10,"drinks":[
                        {"bar":8,"description":null,"name":"Water","score":"4.50","type":"Water"}],
"next":"/api/v1.0/drinks/?page=2","prev":null}

[//]: # (Get single drink info)
<h5>Method: GET</h5>
<h4>URL</h4>
/api/v1.0/drinks/5
<h4>Description</h4>
Get target drink info
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">id</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="left">Drink ID</td>
        </tr>
    </table>
<h4>Response Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">id</td>
            <td align="center">String</td>
            <td align="left">Drink ID</td>
        </tr>
        <tr>
            <td align="center">name</td>
            <td align="center">String</td>
            <td align="left">Drink name</td>
        </tr>
        <tr>
            <td align="center">type</td>
            <td align="center">String (Select?)</td>
            <td align="left">Drink type</td>
        </tr>
        <tr>
            <td align="center">score</td>
            <td align="center">Float (.2)</td>
            <td align="left">Drink score</td>
        </tr>
        <tr>
            <td align="center">description</td>
            <td align="center">String</td>
            <td align="left">Drink derscription</td>
        </tr>
        <tr>
            <td align="center">imageURL</td>
            <td align="center">String</td>
            <td align="left">Link to image</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    GET /api/v1.0/drinks/8/
    curl -u "sl@sl:sl" GET http://localhost:8000/api/v1.0/drinks/5 -H "Accept: application/json"
<h4>Example Response:</h4>

[//]: # (Create new drink)
<h5>Method: POST</h5>
<h4>URL</h4>  /api/v1.0/drinks/
<h4>Description</h4>
Create new drink
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">name</td>
            <td align="center">String</td>
            <td align="left">Drink name</td>
        </tr>
        <tr>
            <td align="center">type</td>
            <td align="center">String (Select?)</td>
            <td align="left">Drink type</td>
        </tr>
        <tr>
            <td align="center">description</td>
            <td align="center">String</td>
            <td align="left">Drink derscription</td>
        </tr>
        <tr>
            <td align="center">imageURL</td>
            <td align="center">String</td>
            <td align="left">Link to image</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    POST /api/v1.0/drinks/
    curl -u "sl@sl:sl" POST http://localhost:8000/api/v1.0/drinks/ -H "Accept: application/json" -d '{"name":"Sprite","type":"Soft","description":"Soft sparkling drink","imageURL":"link_to_image"}'
<h4>Example Response:</h4>
    {"name":"Sprite","type":"Soft","description":"Soft sparkling drink","imageURL":"link_to_image"}

[//]: # (Update drink)

[//]: # (Rate drink)
<h5>Method: POST</h5>
<h4>URL</h4>  /api/v1.0/drinks/7
<h4>Description</h4>
Rate a drink
<h4>Request Parameters</h4>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
        <tr>
            <td align="center">id</td>
            <td align="center">Int</td>
            <td align="center">True</td>
            <td align="center">Drinks ID</td>
        </tr>
        <tr>
            <td align="center">rate</td>
            <td align="center">String</td>
            <td align="center">True</td>
            <td align="center">New rate for drink</td>
        </tr>
    </table>
<h4>Example Request:</h4>
    POST /api/v1.0/drinks/7
    curl -u "sl@sl:sl" POST http://localhost:8000/api/v1.0/drinks/7 -H "Accept: application/json" -d '{"id":"7","rate":"4"}'
<h4>Example Response:</h4>
    {"id":"7","name":"Sprite","type":"Soft","rate":"4.3",description":"Soft sparkling drink","imageURL":"link_to_image"}
-----
<h2>Change Log</h2>
<ul>
    <li><b>04.12.2025:</b> Add API templates </li>
    <li><b>09.01.2026:</b> Add Users, Bars and Drinks main API</li>
    <li><b>10.01.2026:</b> Make all API workable</li>
    <li><b>11.01.2026:</b> Add API for rating the drink</li>
    <li><b>12.01.2026:</b> </li>
    <li><b>..2026:</b></li>
</ul>


--------------
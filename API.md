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
<p>curl -u "<b>mail</b>:<b>password</b>" -H "Accept: application/json" GET http://<b>addres</b>:8000</p>
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
    <tr>
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
    curl -u "sl@sl:sl" -H "Accept: application/json" GET http://localhost:8000/api/v1.0/bars/8
<h4>Example Response:</h4>
    { id:, name: admin_id;,city:, address:, drinks[], rate}
curl: (6) Could not resolve host: GET
{"address":"\u0443\u043b. \u041a\u0443\u0439\u0431\u044b\u0448\u0435\u0432\u0430, 81, \u0421\u0430\u043c\u0430\u0440\u0430, \u0421\u0430\u043c\u0430\u0440\u0441\u043a\u0430\u044f \u043e\u0431\u043b., 443099","city":"\u0421\u0430\u043c\u0430\u0440\u0430","name":"BARSUK"}
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

<h3>User</h3>
<h5>Method: GET</h5>
<h4>URL</h4>
<h4>Description</h4>
<h4>Request Parameters</h4>
<table>
    <tr>
        <th>Name</th>
        <th>Type</th>
        <th>Required</th>
        <th>Description</th>
    </tr>
    <tr>
        <td align="center"></td>
        <td align="center"></td>
        <td align="center"></td>
        <td align="center"></td>
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

<h3>Drink</h3>
<h5>Method: GET</h5>
<h4>URL</h4>
<h4>Description</h4>
<h4>Request Parameters</h4>
<table>
    <tr>
        <th>Name</th>
        <th>Type</th>
        <th>Required</th>
        <th>Description</th>
    </tr>
    <tr>
        <td align="center"></td>
        <td align="center"></td>
        <td align="center"></td>
        <td align="center"></td>
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

-----
<h2>Change Log</h2>
<ul>
    <li><b>04.12.2025:</b> Add API templates </li>
</ul>


--------------
<ul>
<li>Get all bars (pagination 3): GET /api/v1.0/bars/</li>
<li>Get target bar info: GET /api/v1.0/bars/<b>bar_id</b></li>
</ul>
<h4>POST</h4>
<ul>
<li>Create new bar: POST /api/v1.0/bars/</li>
<li>Update bar: POST /api/v1.0/bars/<b>bar_id</b></li>
</ul>


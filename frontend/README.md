# Frontend README

## Frontend structure
Frontend has four different parts: pages, js, css, and test code.<br />

### Pages
Pages are all stored in page folder and each html file stands for a seperate webpage.<br />
login.html: Log in/ register page. Use seperate form-box to seperate them.<br />
index.html: Main page of the web app. Provides links to other pages.<br />
detail.html: Detail page for photos. Show bigger image, location, little map, and follow up questions.<br />
mapView.html: Page with a map showing all photos' locations. Provide link to corresponding detail pages.<br />
upload.html: Upload page support batch upload with zip file and upload with single images.<br />
download.html: Page provides photo downloading with zip format files.<br />

### JS files
JavaScript files are stored in /static/js/ folder. JS files links the backend API and frontend operations.<br />
auth.js: Interact with log in and register API, check valid user input and redirect to main page of this web app.<br />
main.js: Check valid token and handle users' redirect requests. Interact with list, get URL, and search APIs to show photos in grids.<br />
detail.js: Interact with detail info, get URL, submit followup APIs. Show location of the photo and show follow up questions if the photo is labeled as need follow up. Submit users' answers back to the database by calling the submit follow up API.<br />
mapView.js: Show all photos' locations on a single map and providing dynamic interactions with the photo: Show the preview of the photo when using mouse to hover on it. Jump to detail page when the user click the marker. Interacting with both list photos API and OpenstreetMap.<br />
upload.js: Check file type and upload photos by calling upload API. <br />
download.js: Call download API to download selected files.<br />

### css files
Css files provide UI design for the webpages. CSS files are stored in /static/css/ folder and is paired with html and js file.<br />

# Third party files
The frontend uses OpenStreetMap and leaflet to show real-world maps and drop markers on it. The markers are stored in /static/lib/leaflet/images and leaflet settings are stored in /static/lib/leaflet folder.<br />

### Test files
Test files exists for local tests without backend and API. The test files simulates a backend server and provides test for basically all page interactions. Flask server simualtion test code are stored in /frontend folder named frontendtest.py. and other two test files, which simulates data interaction of the server are located at /static/js named test_dataservice.js, and test_photoData.js.<br />

## Frontend deployment
Front end should be deployed on the S3 bucket with exactly same structure:<br />
-login.html<br />
-detail.html<br />
-index.html<br />
-mapView.html<br />
-upload.html<br />
-download.html<br />
--static<br />
----js<br />
------auth.js<br />
------main.js<br />
------upload.js<br />
------download.js<br />
------mapView.js<br />
----css<br />
------auth.css<br />
------detail.css<br />
------download.css<br />
------main.css<br />
------mapView.css<br />
------upload.css<br />
----lib/leaflet<br />
------images/<br />
------leaflet.css<br />
------leaflet.js<br />
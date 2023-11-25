from quart import Quart, request, jsonify

app = Quart(__name__)

# Endpoint that listens for GET requests
@app.route('/')
async def hello():
    return 'Hello, this is a simple REST listener!'

# Endpoint that listens for POST requests
@app.route('/api/data', methods=['POST'])
async def receive_data():
    # Assuming JSON data is sent in the request body
    data = await request.get_json()
    print('Received data:', data)
    return jsonify(message='Data received successfully')

# Run the server on port 5001
if __name__ == '__main__':
    app.run(port=5001, debug=True)
from flask import Flask, render_template, request, redirect
import os, json
app = Flask(__name__)
@app.route('/')
def index(): return render_template('index.html')
app.run('0.0.0.0', port=int(os.getenv('PORT',5000)))
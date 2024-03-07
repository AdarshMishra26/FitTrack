from flask import *
from pymongo import MongoClient
import random
import string
import plotly.graph_objs as go
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bson import ObjectId
import datetime
from flask_mail import *

app = Flask(__name__)
app.secret_key = 'your_secret_key'

with open('config.json') as f:
    params = json.load(f)['param']

# Connect to MongoDB
client = MongoClient("mongodb+srv://adarshmishra:1234@messportal.qrkbtya.mongodb.net/")
db = client['health_tracker']
users_collection = db['users']
activity_collection = db['activity']
exercise_collection = db['exercise']
nutrition_collection = db['nutrition']
goals_collection = db['goals']
progress_collection = db['progress']
social_collection = db['social']
recommendations_collection = db['recommendations']

# Twilio configuration
TWILIO_ACCOUNT_SID = 'ACe0049cacf5a1b63a8c1d0a010d305226'
TWILIO_AUTH_TOKEN = '7d6dc0ca563d357c4980e8f99b96b925'
TWILIO_PHONE_NUMBER = '+18622474305'

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Utility functions
def send_otp(phone, otp):
    try:
        twilio_client.messages.create(
            to=phone,
            from_=TWILIO_PHONE_NUMBER,
            body=f'Your OTP for verification is: {otp}'
        )
        flash('OTP sent successfully.', 'success')
    except Exception as e:
        flash(f'Failed to send OTP: {str(e)}', 'error')

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_email(receiver_email, otp):
    try:
        # Try to login and send email
        server=smtplib.SMTP('smtp.gmail.com',587)
        #adding TLS security 
        server.starttls()
        #get your app password of gmail ----as directed in the video
        sender_email = params['gmail-user']
        password= params['gmail-password']
        server.login(sender_email,password)

        #send
        server.sendmail(sender_email, receiver_email, otp)
        server.quit()

        flash('OTP sent successfully via email.', 'success')
    except Exception as e:
        flash(f'Failed to send OTP via email: {str(e)}', 'error')

def calculate_calories(user_data):
    # Harris-Benedict equation to calculate BMR
    if user_data['gender'] == 'male':
        bmr = 88.362 + (13.397 * user_data['weight']) + (4.799 * user_data['height']) - (5.677 * user_data['age'])
    elif user_data['gender'] == 'female':
        bmr = 447.593 + (9.247 * user_data['weight']) + (3.098 * user_data['height']) - (4.330 * user_data['age'])
    else:
        # Handle other gender options if needed
        bmr = 0

    # Adjust BMR based on activity level to estimate TDEE
    activity_level_multiplier = {
        'sedentary': 1.2,
        'lightly_active': 1.375,
        'moderately_active': 1.55,
        'very_active': 1.725,
        'extra_active': 1.9
    }

    if user_data['activity_level'] in activity_level_multiplier:
        tdee = bmr * activity_level_multiplier[user_data['activity_level']]
    else:
        # Default to sedentary if activity level is not provided
        tdee = bmr * activity_level_multiplier['sedentary']

    return tdee

def generate_recommendations(user_data):
    today = datetime.date.today()
    year, month, date = map(int, user_data['dob'].split('-'))
    age = today.year - year
    recommendations = []

    # Age-based recommendations
    if age < 30:
        recommendations.append("Consider incorporating more high-intensity workouts for better metabolism.")
    elif age >= 30 and user_data['age'] < 50:
        recommendations.append("Focus on maintaining a balanced exercise routine including cardio and strength training.")
    else:
        recommendations.append("Include more flexibility and mobility exercises to maintain joint health.")

    # Weight-related recommendations
    if user_data['weight'] > user_data['ideal_weight']:
        recommendations.append("Try to focus on a calorie deficit diet to reach your ideal weight.")
    elif user_data['weight'] < user_data['ideal_weight']:
        recommendations.append("Ensure you are consuming enough calories to maintain your ideal weight.")
    else:
        recommendations.append("Maintain your current weight by balancing your calorie intake with your energy expenditure.")

    # Activity level recommendations
    if user_data['activity_level'] == 'sedentary':
        recommendations.append("Consider increasing your daily activity level by taking short walks or incorporating light exercises.")
    elif user_data['activity_level'] == 'moderately_active':
        recommendations.append("Continue your current activity level but ensure to maintain a balanced diet to support your lifestyle.")
    elif user_data['activity_level'] == 'very_active':
        recommendations.append("Ensure you are consuming enough calories to fuel your high activity level and consider adding more protein to your diet.")

    # Dietary preferences recommendations
    if 'vegetarian' in user_data['dietary_preferences']:
        recommendations.append("Ensure you are getting enough protein from plant-based sources such as beans, lentils, and tofu.")
    if 'vegan' in user_data['dietary_preferences']:
        recommendations.append("Consider supplementing with vitamin B12 and omega-3 fatty acids as they may be lacking in a vegan diet.")

    # Health condition recommendations (hypothetical examples)
    if 'diabetes' in user_data['health_conditions']:
        recommendations.append("Monitor your carbohydrate intake and aim for balanced meals to manage blood sugar levels.")
    if 'high_blood_pressure' in user_data['health_conditions']:
        recommendations.append("Limit your sodium intake and focus on consuming whole foods rich in potassium and magnesium.")

    return recommendations

# Routes
# Route to render home page
@app.route('/')
def home():
    return render_template('home.html')



# Route to handle forgot password request
@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user_data = users_collection.find_one({'email': email})
        if user_data:
            otp = generate_otp()
            users_collection.update_one({'_id': user_data['_id']}, {'$set': {'otp': otp}})
            # Send OTP via Twilio
            #if send_otp(user_data['phone'], otp):
                #flash('OTP sent successfully via email.', 'success')
                #return redirect(url_for('verify_otp', email=email))
            # Send OTP via email
            send_email(email, otp)
            return render_template('set_password.html')
        else:
            return "Email not found. Please enter a valid email address.", 404
    else:
        return render_template('forgot.html')

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        user_id = ObjectId(session['user'])  # Convert string to ObjectId
        user_data = users_collection.find_one({'_id': user_id})
        
        # Fetch progress data
        progress_data = {
            'activity': list(activity_collection.find({'user_id': user_data['_id']})),
            'exercise': list(exercise_collection.find({'user_id': user_data['_id']})),
            'nutrition': list(nutrition_collection.find({'user_id': user_data['_id']})),
            'goals': list(goals_collection.find({'user_id': user_data['_id']}))
        }

        return render_template('dashboard.html', user=user_data, progress=progress_data)
    else:
        return redirect('/login')
    
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        dob = request.form['dob']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        activity_level = request.form['activity_level']
        dietary_preferences = request.form.getlist('dietary_preferences')
        health_conditions = request.form.getlist('health_conditions')
        weight = float(request.form['weight'])
        height = float(request.form['height'])
        ideal_weight = float(request.form['ideal_weight'])

        if password != confirm_password:
            return render_template('signup.html', message='Passwords do not match')

        otp = generate_otp()

        user_data = {
            'name': name,
            'phone': phone,
            'dob': dob,
            'email': email,
            'password': password,
            'otp': otp,
            'activity_level': activity_level,
            'dietary_preferences': dietary_preferences,
            'health_conditions': health_conditions,
            'weight': weight,
            'height': height,
            'ideal_weight': ideal_weight
        }
        users_collection.insert_one(user_data)

        #send_otp(phone, otp)
        send_email(email, otp)

        flash('Please verify your phone number using the OTP sent to your phone.', 'success')
        return redirect('/verify')

    return render_template('signup.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        otp_entered = request.form['otp']
        user_data = users_collection.find_one({'otp': otp_entered})
        if user_data:
            session['user'] = str(user_data['_id'])  # Convert ObjectId to string
            users_collection.update_one({'_id': user_data['_id']}, {'$unset': {'otp': ''}})
            flash('Verification successful. Welcome!', 'success')
            return redirect('/dashboard')
        else:
            flash('Invalid OTP. Please try again.', 'error')
            return render_template('verify.html')

    return render_template('verify.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' not in session:
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']
            user_data = users_collection.find_one({'email': email, 'password': password})
            if user_data:
                session['user'] = str(user_data['_id'])  # Convert ObjectId to string
                flash('Login successful. Welcome back!', 'success')
                return redirect('/dashboard')  # Redirect to dashboard.html upon successful login
            else:
                flash('Invalid email or password. Please try again.', 'error')
                return render_template('login.html')

        return render_template('login.html')
    else:
        return redirect('/dashboard')

@app.route('/developers')
def developers():
    return render_template('developers.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out successfully.', 'success')
    return redirect('/')

@app.route('/activity', methods=['GET', 'POST'])
def activity():
    if 'user' in session:
        if request.method == 'POST':
            activity_data = request.form.to_dict()
            activity_data['user_id'] = ObjectId(session['user'])  # Convert string to ObjectId
            activity_collection.insert_one(activity_data)
            flash('Activity logged successfully.', 'success')
            return redirect('/dashboard')
        else:
            return render_template('activity.html')
    else:
        return redirect('/login')

@app.route('/exercise', methods=['GET', 'POST'])
def exercise():
    if 'user' in session:
        if request.method == 'POST':
            exercise_data = request.form.to_dict()
            exercise_data['user_id'] = ObjectId(session['user'])  # Convert string to ObjectId
            exercise_collection.insert_one(exercise_data)
            flash('Exercise logged successfully.', 'success')
            return redirect('/dashboard')
        else:
            return render_template('exercise.html')
    else:
        return redirect('/login')

@app.route('/nutrition', methods=['GET', 'POST'])
def nutrition():
    if 'user' in session:
        if request.method == 'POST':
            nutrition_data = request.form.to_dict()
            nutrition_data['user_id'] = ObjectId(session['user'])  # Convert string to ObjectId
            nutrition_collection.insert_one(nutrition_data)
            flash('Nutrition logged successfully.', 'success')
            return redirect('/dashboard')
        else:
            return render_template('nutrition.html')
    else:
        return redirect('/login')

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if 'user' in session:
        if request.method == 'POST':
            goals_data = request.form.to_dict()
            goals_data['user_id'] = ObjectId(session['user'])  # Convert string to ObjectId
            goals_collection.insert_one(goals_data)
            flash('Goals updated successfully.', 'success')
            return redirect('/dashboard')
        else:
            return render_template('goals.html')
    else:
        return redirect('/login')

@app.route('/progress')
def progress():
    if 'user' in session:
        user_data = users_collection.find_one({'_id': ObjectId(session['user'])})  # Convert string to ObjectId
        progress_data = {
            'activity': list(activity_collection.find({'user_id': user_data['_id']})),
            'exercise': list(exercise_collection.find({'user_id': user_data['_id']})),
            'nutrition': list(nutrition_collection.find({'user_id': user_data['_id']})),
            'goals': list(goals_collection.find({'user_id': user_data['_id']}))
        }
        return render_template('progress.html', progress=progress_data)
    else:
        return redirect('/login')

@app.route('/social')
def social():
    if 'user' in session:
        return render_template('social.html')
    else:
        return redirect('/login')

@app.route('/recommendations')
def recommendations():
    if 'user' in session:
        user_data = users_collection.find_one({'_id': ObjectId(session['user'])})  # Convert string to ObjectId
        recommendations_data = generate_recommendations(user_data)
        return render_template('recommendations.html', recommendations=recommendations_data)
    else:
        return redirect('/login')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' in session:
        if request.method == 'POST':
            user_id = ObjectId(session['user'])  # Convert string to ObjectId
            update_data = {
                'name': request.form['name'],
                'phone': request.form['phone'],
                'dob': request.form['dob'],
                'email': request.form['email'],
                'activity_level': request.form['activity_level'],
                'dietary_preferences': request.form.getlist('dietary_preferences'),
                'health_conditions': request.form.getlist('health_conditions'),
                'weight': float(request.form['weight']),
                'height': float(request.form['height']),
                'ideal_weight': float(request.form['ideal_weight'])
            }
            users_collection.update_one({'_id': user_id}, {'$set': update_data})
            flash('Profile updated successfully.', 'success')
            return redirect('/dashboard')
        else:
            user_data = users_collection.find_one({'_id': ObjectId(session['user'])})  # Convert string to ObjectId
            return render_template('profile.html', user=user_data)
    else:
        return redirect('/login')

# Forgot.html
@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    if request.method == 'POST':
        otp_entered = request.form['otp']
        # Retrieve user data from the database based on the entered OTP
        user_data = users_collection.find_one({'otp': otp_entered})
        if user_data:
            # OTP verification successful
            session['user'] = str(user_data['_id'])  # Store user ID in session
            # Clear the OTP from the database or mark it as verified
            users_collection.update_one({'_id': user_data['_id']}, {'$unset': {'otp': ''}})
            return jsonify({'success': True}), 200
        else:
            # Invalid OTP
            return jsonify({'success': False}), 400
    else:
        # Invalid request method
        return jsonify({'success': False, 'message': 'Invalid request method'}), 405


@app.route('/reset_password', methods=['POST'])
def reset_password():
    if 'user_id' in session:
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if new_password == confirm_password:
            # Update password in the database
            user_id = ObjectId(session['user_id'])
            users_collection.update_one({'_id': user_id}, {'$set': {'password': new_password}})
            flash('Password reset successfully.', 'success')
            return redirect('/login')
        else:
            flash('Passwords do not match. Please try again.', 'error')
    else:
        flash('Session expired. Please try again.', 'error')
    return redirect('/forgot')

if __name__ == '__main__':
    app.run(debug=True)

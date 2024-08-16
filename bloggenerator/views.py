import filetype
import logging
import os
import json
from yt_dlp import YoutubeDL
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from pytube import YouTube
from django.conf import settings
import assemblyai as aai
from moviepy.editor import VideoFileClip

import google.generativeai as genai
from .models import BlogPost
from django.shortcuts import get_object_or_404

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Create your views here.
def home(request):
    return render(request, 'index.html')

@login_required
def dashboard(request):
    return render(request, 'home.html')



@csrf_exempt
def is_video_file(file):
    try:
        kind = filetype.guess(file.read())
        file.seek(0)  # Reset file pointer to the start
        return kind and kind.mime.startswith('video/')
    except Exception as e:
        logging.error(f"Error determining file type: {e}", exc_info=True)
        return False
@login_required
@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            youtube_link = request.POST.get('youtube_link')
            file = request.FILES.get('file')

            if youtube_link:
                # Handle YouTube link
                title = yt_title(youtube_link)

                # Get the transcription from the YouTube video
                transcription = get_transcription(youtube_link)
                if not transcription:
                    return JsonResponse({'error': 'Failed to get transcription'}, status=500)

                # Generate the blog content
                blog_content = generate_blog_from_transcription(transcription)
                if not blog_content:
                    return JsonResponse({'error': 'Failed to generate blog article'}, status=500)

                # Save the blog article
                new_blog_article = BlogPost.objects.create(
                    user=request.user,
                    youtube_title=title,
                    youtube_link=youtube_link,
                    transcript=transcription,
                    generated_content=blog_content
                )
                new_blog_article.save()

            elif file:
                # Handle file upload (audio/video)
                title = file.name
                file_path = save_file(file)  # Custom function to save the file and return the path

                # Check if the file is a video
                if is_video_file(file):
                    audio_file_path = extract_audio_from_video(file_path)  # Custom function to extract audio
                else:
                    audio_file_path = file_path

                # Get the transcription from the file
                transcription = get_transcription_from_file(audio_file_path)
                if not transcription:
                    return JsonResponse({'error': 'Failed to get transcription'}, status=500)

                # Generate the blog content
                blog_content = generate_blog_from_transcription(transcription)
                if not blog_content:
                    return JsonResponse({'error': 'Failed to generate blog article'}, status=500)

                # Save the blog article
                new_blog_article = BlogPost.objects.create(
                    user=request.user,
                    youtube_title=title,
                    youtube_link=file_path,  # Store the file path in youtube_link
                    transcript=transcription,
                    generated_content=blog_content
                )
                new_blog_article.save()

            else:
                return JsonResponse({'error': 'You must provide either a YouTube link or upload a file'}, status=400)

            # Return the generated blog content as a response
            return JsonResponse({"content": blog_content})

        except (KeyError, json.JSONDecodeError) as e:
            logging.error(f"Error processing POST data: {e}")
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        except Exception as e:
            logging.error(f"Unexpected error: {e}", exc_info=True)
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def extract_audio_from_video(video_path):
    try:
        # Load the video file
        video = VideoFileClip(video_path)

        # Extract the audio
        audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
        video.audio.write_audiofile(audio_path)

        return audio_path

    except Exception as e:
        logging.error(f"Error extracting audio from video: {e}", exc_info=True)
        return None

def yt_title(link):
    try:
        yt = YouTube(link)
        title = yt.title
        return title
    except Exception as e:
        logging.error(f"Error fetching YouTube title: {e}")
        return None

def download_audio(link):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(settings.MEDIA_ROOT, '%(title)s.%(ext)s'),
            'retries': 5,  # Retry up to 5 times
            'timeout': 60,  # Increase timeout to 60 seconds
        }

        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=True)
            file_path = ydl.prepare_filename(info_dict)
            base, ext = os.path.splitext(file_path)
            new_file = base + '.mp3'

            # Check if the file already exists and rename it if necessary
            if os.path.exists(new_file):
                base = f"{base}_{info_dict['id']}"
                new_file = base + '.mp3'

            os.rename(file_path, new_file)
            logging.info(f"File renamed successfully: {new_file}")

        return new_file

    except Exception as e:
        logging.error(f"Error in download_audio function: {e}", exc_info=True)
        return None


def save_file(file):
    file_name = file.name
    file_path = os.path.join('media/', file_name)
    with open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    return file_path

def get_transcription(link):
    try:
        audio_file = download_audio(link)
        if not audio_file:
            return None

        aai.settings.api_key =  settings.AAI_API_KEY # Use Django settings for API key
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_file)
        return transcript.text

    except Exception as e:
        logging.error(f"Error in get_transcription function: {e}", exc_info=True)
        return None
    
def get_transcription_from_file(file_path):
    try:
        # Ensure the file exists and is accessible
        if not os.path.exists(file_path):
            logging.error(f"File not found: {file_path}")
            return None

        # Set up the API key for transcription service
        aai.settings.api_key =settings.AAI_API_KEY    # Use Django settings for API key

        # Create the transcriber object
        transcriber = aai.Transcriber()

        # Transcribe the file
        with open(file_path, 'rb') as audio_file:
            transcript = transcriber.transcribe(audio_file)

        return transcript.text

    except Exception as e:
        logging.error(f"Error in get_transcription_from_file function: {e}", exc_info=True)
        return None

def generate_blog_from_transcription(transcription):
    try:
        # Define your Google Gemini API key here
        gemini_api_key = settings.GEMINI_API_KEY 
        genai.configure(api_key=gemini_api_key)

        # Structure the transcription into a prompt
        transcription_text = f"""
        Create a blog article from the provided transcript:

        {transcription}
        Structure the article as follows:
        1.	Introduction
	        Briefly introduce the main topic or theme of the discussion.
       2.	Body:
           	Summarize the content based on timestamps.
        	For each timestamp, provide a concise summary or key points discussed.
       3.	Conclusion:
	        Summarize the key takeaways from the discussion.
        Format:
	        Use clear headings and subheadings for different timestamps.
            Write in an engaging and professional tone.
            Example of Input Transcript:
                "00:00:00 - Introduction to AI 00:02:15 - Recent Technological Advances 00:05:30 - AI in Healthcare 00:08:45 - Ethical Issues 00:12:00 - Future Outlook"

	

        """

        # # Define the endpoint and headers for Google Gemini API
        # gemini_endpoint = "https://gemini.googleapis.com/v1beta1/projects/your-project-id/locations/your-location/gemini-text-generate"
        # headers = {
        #     "Authorization": f"Bearer {gemini_api_key}",
        #     "Content-Type": "application/json"
        # }
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Define the payload for the API request
        generation_config = genai.types.GenerationConfig(
            candidate_count=1,          # Generate only one candidate
            stop_sequences=["in Conclusion", "\n\n\n\n\n"],       # Stop sequence (adjust as needed)
            max_output_tokens=1000,       # Set a limit on the output tokens
            temperature=0.5             # Control the randomness (adjust as needed)
        )

        # Generate content using the transcription text as the prompt
        response = model.generate_content(
            transcription_text,
            generation_config=generation_config
        )

        # Extract the generated content
        generated_content = response.text
        print(generated_content)

        return generated_content

    except Exception as e:
        logging.error(f"Error in generate_blog_from_transcription function: {e}", exc_info=True)
        return None
@login_required
def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request,'allblogpost.html',{'blog_articles':blog_articles})
@login_required
def blog_details(request,pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request,'blogdetails.html',{'blog_article_detail':blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)
        if user is not None:
            user.backend = 'django.contrib.auth.backends.ModelBackend'  # Specify the backend explicitly
            login(request, user)
            logging.info(f"The user logged in is: {user}")
            return redirect('/dashboard')
        else:
            logging.warning("Login failed")
            error_message = "Invalid user. Please sign up if you don't have an account."
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password == confirm_password:
            if User.objects.filter(email=email).exists():
                error_message = 'A user with this email already exists.'
                logging.warning(f"Attempted registration with existing email: {email}")
                return render(request, 'register.html', {'error_message': error_message})

            try:
                user = User.objects.create_user(username=username, email=email, password=password)
                user.save()

                user.backend = 'django.contrib.auth.backends.ModelBackend'  # Specify the backend explicitly
                login(request, user)

                logging.info(f"User registered and logged in: {user}")
                return redirect('/dashboard')

            except Exception as e:
                logging.error(f"Error registering user: {e}")
                error_message = 'Error occurred while registering the user. Please try again.'
                return render(request, 'register.html', {'error_message': error_message})

        else:
            error_message = 'Passwords do not match.'
            logging.warning(f"Password mismatch for email: {email}")
            return render(request, 'register.html', {'error_message': error_message})

    else:
        # Handle GET request by rendering the signup form
        return render(request, 'register.html')
@login_required
def user_logout(request):
    logout(request)
    return redirect('/login/')
@login_required
@csrf_exempt
def delete_blog(request, blog_id):
    if request.method == 'POST':
        try:
            blog = get_object_or_404(BlogPost, id=blog_id)
            blog.delete()
            return redirect('/blog-posts/')
            # return JsonResponse({"success": True, "message": "Blog deleted successfully"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    # return JsonResponse({"success": False, "message": "Invalid request method"})
    return redirect('/blog-posts/')

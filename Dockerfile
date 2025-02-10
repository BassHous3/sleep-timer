# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install tzdata package for timezone support
RUN apt-get update && apt-get install -y tzdata

# Set the timezone based on the TZ environment variable
ENV TZ=${TZ:-UTC}

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5553 available to the world outside this container
EXPOSE 5553

# Copy the .env file into the container
#COPY .env .env
ENV MOVIES_ONLY=False
ENV EPISODES_ONLY=True
ENV CONFIRMATION_TIMEOUT=60
ENV MAXIMUM_PLAYTIME_ALLOWED=120

# Run app.py when the container launches
CMD ["gunicorn", "-b", "0.0.0.0:5553", "--access-logfile", "-", "app:app"]

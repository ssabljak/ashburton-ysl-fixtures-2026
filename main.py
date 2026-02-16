# Updated main.py with refactored code

# Main code starts here

# Function to generate logo

def generate_logo(data):
    # Implementation for logo generation
    pass

# Index generation related code

def generate_index(data):
    # Implementation for generating index.html file
    pass

# Assuming teams_data is a list of team info

# Generate logo and index.html outside the loop
logo = generate_logo(teams_data)  # Generate logo once

# Now we can loop through the teams to create other components
for team in teams_data:
    # Process team data and create necessary files
    # create_team_files(team)

# Generate index.html with the logo
generate_index(logo)
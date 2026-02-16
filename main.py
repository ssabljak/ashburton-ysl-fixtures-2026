import json
import os
from jinja2 import Environment, FileSystemLoader

# Function to generate logo

def generate_logo(team_name):
    return f"<h1>{team_name}</h1>\n<img src='path/to/logo/{team_name}.png' alt='{team_name} Logo'>"

# Function to generate index.html

def generate_index_html(content, team_name):
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('index.html')
    with open(f'output/{team_name}/index.html', 'w') as f:
        f.write(template.render(content=content, team_name=team_name))

# Main processing function

def main():
    teams = json.load(open('teams.json'))
    for team in teams:
        team_name = team['name']
        logo = generate_logo(team_name)
        # Assuming content generation logic here...
        content = f"{logo}<p>This is the content for {team_name}</p>"
        # Generate index.html for each team
        generate_index_html(content, team_name)

if __name__ == '__main__':
    if not os.path.exists('output'):
        os.makedirs('output')
    main()
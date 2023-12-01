

import asyncio
import datetime
import json
import math

import requests
from broadcaster import Broadcaster
from logger import Logger


class Vote:
    broadcaster: Broadcaster
    voted: list
    endpoint:str
    
    def __init__(self, broadcaster: Broadcaster, l:Logger, endpoint:str) -> None:
        self.broadcaster = broadcaster
        self.l = l
        self.isRunning = False
        self.choice = []
        self.voted = []
        self.vote_on_going = False
        self.endpoint = endpoint
        
        
        
        pass
    
    def reset_choices(self):
        self.l.info(f'Resetting Vote for {self.broadcaster.twitch_login}')
        self.choice = []
        for i in range(4):
            self.choice.append(0)
        self.voted = []
    
    async def vote(self):
        self.l.info(f'Voting enabled for {self.broadcaster.twitch_login} {self.isRunning}')
        self.reset_choices()

        while self.isRunning:
            await asyncio.sleep(2)
            self.l.info(f'Vote for {self.broadcaster.twitch_login} Started, waiting on spawn')

            vote_start = asyncio.get_event_loop().time()

            while self.vote_on_going:
                await asyncio.sleep(1)
                elapsed_time = asyncio.get_event_loop().time() - vote_start
                remaining_time = max(0, 30 - elapsed_time)

                self.l.info(f'Vote for {self.broadcaster.twitch_login} Updating')
                await self.update_vote(math.floor(remaining_time))

                if remaining_time <= 0:  # time to vote
                    await self.end_vote()
                    await asyncio.sleep(120)  # time till next vote

        self.l.info(f'Voting stopped for {self.broadcaster.twitch_login} {self.isRunning}')
        
        
    async def update_vote(self, time:int):
        self.l.info(f'Updated vote for {self.broadcaster.twitch_login}')
        
        data = {
            "EventType": "VoteOnGoing",
            "SteamId": self.broadcaster.steam_id,
            "Choices": self.choice,
            "Time": time
        }
        await self.POST(data)
    
    async def end_vote(self):
        self.l.info(f'Ended vote for {self.broadcaster.twitch_login}')
        
        data = {
            "EventType": "VoteEnd",
            "SteamId": self.broadcaster.steam_id,
            "Choices": self.choice
        }
        await self.POST(data)
        self.reset_choices()
        
        
    async def POST(self, data):
        # Convert the data to JSON format
        json_data = json.dumps(data)

        self.l.info(f'Data ready to send: {json_data}')
        

        # Make the POST request
        response = requests.post(self.endpoint, json=json_data)

        # Check if the request was successful (status code 2xx)
        if response.ok:
            return f'Sucessfully updated Vote for {self.broadcaster.twitch_login}({self.broadcaster.steam_id})'
        else:
            # If the request was unsuccessful, raise an exception with the error message
            response.raise_for_status()
            return f'Error updating Vote for {self.broadcaster.twitch_login}({self.broadcaster.steam_id})'
        
    
    async def register_vote(self, choice:int):
        self.l.info("Registering Vote")
        self.choice[choice] = self.choice[choice]+1
#!/usr/bin/python3

import requests
import traceback
import readline # To get over 4k chars for input

sess_req = requests.Session()

def send_request(message):
    data_to_send = {"message": message}
    # print("Message length to send is %d" % len(message))
    # print(sess_req.cookies.get_dict())
    response = sess_req.post("http://www.drako.ai/api/send_message", data=data_to_send)
    # print(response)
    # print(response.text)
    response_json = response.json()

    # print(response)
    response_message = response_json['message']
    if 'cards' in response_json:
        cards = response_json['cards']
    else:
        cards = []

    return response_message, cards

def main():
    print("Will start chat shell!")
    while True:
        try:
            input_str = input("User: ")
            if input_str.lower() == "exit":
                print("Exiting...")
                break
            response, cards  = send_request(input_str)
            print("Drako: %s" % response)
            print("===== Cards: %s =====" % cards)
            print("\n\n\n")
        except:
            print("ERROR => %s" % traceback.format_exc())

main()
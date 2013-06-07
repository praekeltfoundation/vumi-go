Sample Applications
===================

A number of example applications have been built that highlight different
bits of functionality.

**Ushahidi**

This is an application that exposes the functionality of Ushahidi over USSD.
It allows submission of reports via a USSD menu and uses Google Maps' API
for geolocation based on raw address input.

source
    https://github.com/smn/go-ushahidi

demo
    Available in South Africa on ``*120*8864*1087#``, interacts with
    http://vumi.crowdmap.com/

**Google Maps Directions**

This application allows people to receive directions from Google Maps' API.
It asks where the user currently is and where they want to go. Using Google's
API a geolocation is done on the raw input and the directions are sent to the
user via SMS.

source
    https://github.com/smn/go-google-maps

demo
    Available in South Africa on ``*120*8864*1105#``.
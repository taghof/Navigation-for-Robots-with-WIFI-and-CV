---
layout: post
title: Drone Navigation Wörterbuch
public: false
---

Location Node
=============
A location in the real world, a Node is defined by a collection of locally measured filtered radio source signal strength readings (WIFI point), possibly a collection of visible recognisable salient features a Distance map, together with the nodes relation to other neighbouring Location Nodes (wrt. direction and distance).

WIFI Point
==========
A collection of WIFI signal strength samples that have been filtered acording to a quality measurement. Samples are taken at a single position in real-world space. In some litterature the concept is known as a reference point, set up in an offline phase, as a training point etc (Indoor GSM, RADAR).

Radio source ID
===============
In this context the ID is a Mac-address of a WIFI Access point, PC or other WIFI enabled device. One could possily use other forms of radio sources (eg. GSM, FM, etc) here however we just use 802.11.

SS Reading
==========
A single signal strength reading originating from an Wireless device in hearing distance from the current location, taken at a specific timestamp.

WIFI Sample
===========
A momentary sample of an unfiltered collection of signal strengths with their associated Device IDs. In some literature known as a testing point or a sample gathered in an online phase.

Sample Score
============
A function takes a WIFI Sample and a WIFI point and compares the two, returning a score value between 0 and 100 procent, telling how good the two arguments match up (the idea is similar to a sort of localization algorithm, that try to estimate a client location).

Locale Distance Map
===================
Not fully and completely formulated yet, this maps differences in two 2D images taken at different angles into distances from camera two recognizable features detected in the two images.

Node-Graph
==========
A Graph holding Location Nodes. Two nodes are connected by edges only if they can be travelled between without visiting other nodes on the way. It is possible to update, maybe optimize the graph over time with new Location nodes and new edges, also by removing edges an nodes.

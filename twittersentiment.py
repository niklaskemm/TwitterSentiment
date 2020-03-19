import json
import time
import re
import textblob
import pandas as pd
import geopandas as gpd
import altair as alt
from vega_datasets import data
from collections import defaultdict
from tweepy import Stream, OAuthHandler
from tweepy.streaming import StreamListener

# defining GLOBAL VARIABLES
_OUTPUT_JSON_FILENAME = f'{time.strftime("%Y%m%d-%H%M%S")}.json'
_RESULTS_DICT_JSON = defaultdict(list)


class Listener(StreamListener):
    """
    StreamListener class of the Tweepy module. Used to actually stream data.
    """

    def on_data(self, data):
        """
        Function that processes the received data / tweets.

        Splits the received data into several parts fpr further processing and
        appends it to the _RESULTS_DICT_JSON defaultdict list. Always returns
        True to not stop the stream.

        Args:
            data: Actual chuncks of data that are received.

        Returns:
            True
        """
        try:
            # loading the data as a dictionary for easier access
            jr = json.loads(data)

            # extracting the different keys from the response
            date = jr["created_at"]
            geo = jr["geo"]

            coord = geo["coordinates"]
            coord_lat = geo["coordinates"][0]
            coord_lon = geo["coordinates"][1]
            coord_clean = f"{coord_lon}, {coord_lat}"

            user = jr["user"]
            user_name = user["name"]
            user_id = user["id"]

            # the source field cannot be represented by a dictionary
            # therefore it is extracted using multiple splits
            source = data.split('\\"\\u003e')[1].split('\\u003c\\/a')[0]
            # matching the source
            source_cleaned = clean_source(source)

            text = jr["text"]
            # cleaning the text
            text_clean = clean_tweet(text)
            # analyzing the sentiment
            sentiment = get_tweet_sentiment(text_clean)

            # Used for DEBUGGING only!
            # result_screen = f"{user_name} at \
            #    {coord_clean}: {text} ({sentiment})({source})"

            if coord != "null":
                # Used for DEBUGGING only!
                # print(result_screen, "\n")

                # creating new dict with the relevant information
                result = {
                    "date": date,
                    "user_name": user_name,
                    "user_id": user_id,
                    "coord_clean": coord_clean,
                    "coord_lat": coord_lat,
                    "coord_lon": coord_lon,
                    "text": text,
                    "text_clean": text_clean,
                    "sentiment": sentiment,
                    "source": source,
                    "source_clean": source_cleaned
                }

                # appending the single results to the general data json
                _RESULTS_DICT_JSON["data"].append(result)
            return True

        # catches any exception that might occur and skips the tweet
        except Exception:
            # used for DEBUGGING only!
            # print(Exception)
            return True

    def on_error(self, status):
        """
        Generic error function that prints the Error Message.

        Args:
            status: Status code of the error.

        Returns:
            False
        """
        if status == 420:
            return False


def get_auth(filename="auth.json"):
    """
    Function to validate the authentication credentials.

    Args:
        filename: Defaults to 'auth.json'. JSON-file with keys 'consumer_key',
            'consumer_secret', 'access_secret' and 'access_token'.

    Returns:
        auth: OAuthHandler token.
    """
    # open the file and translate into dict
    with open(filename, "r") as f:
        file = json.load(f)
    # extracting the consumer key and secret
    ckey, csecret = file["consumer_key"], file["consumer_secret"]
    # setting the consumer key and secret
    auth = OAuthHandler(ckey, csecret)
    # extracting the access token and secret
    atoken, asecret = file["access_token"], file["access_secret"]
    # setting the access token and secret
    auth.set_access_token(atoken, asecret)

    return auth


def clean_tweet(tweet):
    """
    Function to clean tweet of unwanted characters and links.

    Credits: Nikhil Kumar @ GeeksforGeeks
    (https://www.geeksforgeeks.org/twitter-sentiment-analysis-using-python/)
    Cleans the tweets by substituting any
    Mentions (@[A-Za-z0-9]+) [@ followed by at least one of A-Z, a-z or 0-9],
    Special characters at the start ([^0-9A-Za-z \t]) [not in A-Z, a-z, 0-9,
        or a variation of spaces (\t)], as well as
    URLs.

    Args:
        tweet: Text representation of the tweet.

    Returns:
        tweet_cleaned: Cleaned-up version of the tweet.
    """
    tweet_cleaned = ' '.join(re.sub(
        "(@[A-Za-z0-9]+)|([^0-9A-Za-z \t])|(\w+:\/\/\S+)", " ", tweet
    ).split())

    return tweet_cleaned


def get_tweet_sentiment(tweet):
    """
    Function to analyze the polarity/sentiment of a tweet.

    Args:
        tweet: Text-representation of tweet that shall be analyzed.

    Returns:
        'positive': If polarity of tweet is > 0.
        'negative': If polarity of tweet is < 0.
        'neutral': If polarity of tweet is = 0.
        False: If polarity can not be determined.
    """
    try:
        # transform the tweet into a TextBlob object
        analysis = textblob.TextBlob(tweet)
        # get the polarity of the object
        polarity = analysis.sentiment.polarity
        if analysis != "":
            if polarity > 0:
                return 'positive'
            elif polarity < 0:
                return 'negative'
            else:
                return 'neutral'

    except Exception as e:
        print("No analysis possible: " + str(e))
        return False


def clean_source(source):
    """
    Function to compromize different sources of tweets into classes.

    Function that matches different sources of tweets against pre-defined
    classes for better visualization of sources in the final maps and diagrams.
    The pre-defined classes are:
        'Twitter for Android'
        'Twitter for iPhone'
        'Twitter for Windows Phone'
        'Instagram'
        'Foursquare' (Consising of both 'Foursquare' and 'Foursquare Swarm')
        'Other' (Consisting of any other source)

    Args:
        source: Text-representation of source of tweet.

    Returns:
        source_clean: Text-representation of source class.
    """

    # defining the sources that should not be changed
    source_list = (
        "Twitter for Android",
        "Twitter for iPhone",
        "Twitter for Windows Phone",
        "Instagram"
    )

    if source in source_list:
        source_clean = source
    elif source == ("Foursquare" or "Foursquare Swarm"):
        source_clean = "Foursquare"
    else:
        source_clean = "Other"

    return source_clean


def get_data(location, auth_file="auth.json"):
    """
    Function that starts the stream and saves the processed data.

    Args:
        location: Bounding box of the area that the tweets shall come from.
        auth_file: Defaults to 'auth.json'. JSON-file with keys 'consumer_key',
            'consumer_secret', 'access_secret' and 'access_token'.
    """
    # creating Stream Instance
    twitterStream = Stream(get_auth(auth_file), Listener())

    # starting the Stream
    try:
        print('Start streaming...')
        twitterStream.filter(locations=location)

    # handling the necessary KeyboardInterrupt to stop the stream
    # Stopping the Kernel in Jupyter causes KeyboardInterrupt aswell
    except KeyboardInterrupt:
        print("Stop streaming...")

    except Exception as e:
        print("Error :", e)

    # always save the data!
    finally:
        print("Stop streaming...")
        with open("data/" + _OUTPUT_JSON_FILENAME, "w") as f:
            # dumping the data into an external JSON file
            json.dump(_RESULTS_DICT_JSON, f, indent=2)
        print(f"Output file data/'{_OUTPUT_JSON_FILENAME}' generated")
        print(f"Number of collected tweets: {len(_RESULTS_DICT_JSON['data'])}")
        # disconnecting the stream
        twitterStream.disconnect()
        print('Done.')


def create_dataframe_world(data=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Utility function to create a pandas dataframe from a JSON file.

    Args:
        data: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        dataframe: Pandas dataframe with columns corresponding to keys of JSON.
    """
    dataframe = pd.read_json(data, orient="split")
    return dataframe


def create_dataframe_us(data=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Utility function to create a geopandas dataframe from a JSON file.

    The function creates a geopandas dataframe from the given data and returns
    all tweets that were sent from the US.

    Args:
        data: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        dataframe: Geopandas dataframe of all tweets from the US
            with columns corresponding to keys of JSON.
    """
    dataframe = pd.read_json(data, orient="split")

    # create geopandas dataframe from pandas dataframe
    gdf_tweets = gpd.GeoDataFrame(dataframe, geometry=gpd.points_from_xy(
        dataframe.coord_lon, dataframe.coord_lat))
    # change the crs of the dataframe
    gdf_tweets.crs = {'init': 'epsg:4326'}

    # create gpd_df for the states of the US
    gdf_states = gpd.read_file("us-states.geojson")
    # deleting all columns besides 'name' and 'geometry'
    gdf_states = gdf_states[["name", "geometry"]]
    # change the crs of the dataframe
    gdf_states.crs = {'init': 'epsg:4326'}

    # spatially join the two dataframes
    dataframe = gpd.sjoin(
        gdf_states, gdf_tweets, how="inner", op='intersects'
    )

    return dataframe


def create_dataframe_choropleth(data=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Utility function to create a geopandas dataframe from a JSON file.

    The function takes the intial JSON file and joins the tweets with
    the states of the US and aggregates the polarity/sentiment into
    the mean values per state.

    Args:
        data: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        gdf_final: Geopandas dataframe containing of the states' name and
            polarity/sentiment.
    """
    # use create_dataframe() function to generate intitial dataframe from data
    df = create_dataframe_world(data)
    # create geopandas dataframe from pandas dataframe
    gdf_tweets = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(
        df.coord_lon, df.coord_lat))
    # delete all columns besides 'sentiment' and 'geometry'
    gdf_tweets = gdf_tweets[["sentiment", "geometry"]]
    # change the crs of the dataframe
    gdf_tweets.crs = {'init': 'epsg:4326'}
    # replacing the sentiment string with corresponding absolute numbers
    gdf_tweets = gdf_tweets.replace({"positive": 1, "negative": -1,
                                     "neutral": 0, "False": None})

    # create gpd_df for the states of the US
    gdf_states = gpd.read_file("us-states.geojson")
    # deleting all columns besides 'name' and 'geometry'
    gdf_states = gdf_states[["name", "geometry"]]
    # change the crs of the dataframe
    gdf_states.crs = {'init': 'epsg:4326'}

    # spatially join the two dataframes
    gdf_tweets_with_states = gpd.sjoin(
        gdf_states, gdf_tweets, how="inner", op='intersects'
    )
    # deleting all columns besides 'name', 'sentiment' and 'geometry'
    gdf_tweets_with_states = gdf_tweets_with_states[
        ["name", "sentiment", "geometry"]
    ]
    # change types of columns for calculation and display with altair
    gdf_tweets_with_states = gdf_tweets_with_states.astype(
        {'sentiment': 'int32', "name": "object"}
    )
    # renaming the 'name' column for better visual representation
    # on mouse-over in the final map
    gdf_tweets_with_states["State"] = gdf_tweets_with_states["name"]

    # aggregate the sentiment on per state basis
    gdf_states_with_sentiment = gdf_tweets_with_states.dissolve(
        by="name", aggfunc="mean"
    )
    # change the crs of the dataframe
    gdf_states_with_sentiment.crs = {'init': 'epsg:4326'}

    # second join to display Alaska aswell
    gdf_final = gpd.sjoin(
        gdf_states_with_sentiment, gdf_states, how="inner", op="within"
    )

    return gdf_final


def plot_tweets_world(dataset=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Function to plot all tweets worldwide as points using altair.

    Args:
        dataset: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        output_map: map that represents the world and all tweets.
    """
    # calling utility function to create dataframe
    df = create_dataframe_world(dataset)
    # using vega_datasets(data) to get the borders of the countries
    countries = alt.topo_feature(data.world_110m.url, feature='countries')
    # using altair function to create a spherical background
    sphere = alt.sphere()

    # disable the maximum rows restriction to be able to chart larger datasets
    alt.data_transformers.disable_max_rows()

    # generating chart consisting of the spherical background
    spheric_background = alt.Chart(sphere).mark_geoshape(fill="aliceblue")

    # generating chart consisting of the countries
    background_world = alt.Chart(countries).mark_geoshape(
        fill='lightgray',
        stroke='white'
    ).properties(
        width=720,
        height=400
    )

    # generating chart consisting of the tweets
    points_world = alt.Chart(df).mark_square(size=1, opacity=0.8).encode(
        # setting the lat/lon
        longitude="coord_lon",
        latitude="coord_lat",
        color=alt.Color("sentiment:N",
                        # matching the classes onto the sentiment
                        scale=alt.Scale(domain=[
                            "positive", "neutral", 'negative'
                        ],
                            # colouring the classes
                            range=["green", "orange", "red"]
                        )
                        ),
        # generating tooltip with the user name, text and sentiment of tweet
        tooltip=["user_name", "text", "sentiment"]
    )

    # generating the final layered chart
    output_map = (spheric_background + background_world + points_world)\
        .project("naturalEarth1")

    return output_map


def plot_tweets_usa(dataset=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Function to plot all tweets of the US as points using altair.

    Args:
        dataset: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        output_map: map of the US and the tweets sent from there.
    """
    # calling utility function to create dataframe
    df = create_dataframe_us(dataset)
    # using vega_datasets(data) to get the borders of the states of the US
    states = alt.topo_feature(data.us_10m.url, feature="states")

    # disable the maximum rows restriction to be able to chart larger datasets
    alt.data_transformers.disable_max_rows()

    # generating chart consisting of the states
    background_usa = alt.Chart(states).mark_geoshape(
        fill="lightgray",
        stroke="white"
    ).properties(
        width=720,
        height=400
    )

    # generating chart consisting of the tweets from the US
    points_usa = alt.Chart(df).mark_square(size=5, opacity=0.5).encode(
        longitude="coord_lon",
        latitude="coord_lat",
        color=alt.Color("sentiment:N",
                        scale=alt.Scale(domain=[
                            "positive", "neutral", "negative"
                        ],
                            range=["green", "orange", "red"]
                        )),
        tooltip=["user_name", "text", "sentiment"]
    )

    # generating the final layered chart
    output_map = (background_usa + points_usa).project("albersUsa")

    return output_map


def plot_stats_world(dataset=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Function to plot the number of tweets per source.

    Args:
        dataset: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        overview: Interactive Horizonztal bar chart with
            the number of tweets per source.
    """
    # calling utility function to create dataframe
    df = create_dataframe_world(dataset)

    # disable the maximum rows restriction to be able to chart larger datasets
    alt.data_transformers.disable_max_rows()

    # generating horizontal bar chart
    overview = alt.Chart(df).mark_bar().encode(
        # defining the column to class by
        alt.Y("source_clean:N",
              title="sources"
              ),
        # aggregating the number of tweets per class
        alt.X("count()"),
        tooltip="count()"
    ).properties(width=720)

    return overview


def plot_stats_usa(dataset=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Function to plot the number of tweets per source of the US.

    Args:
        dataset: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        overview: Horizonztal bar chart with the number
            of tweets per source of the US.
    """
    # calling utility function to create dataframe
    df = create_dataframe_us(dataset)

    # disable the maximum rows restriction to be able to chart larger datasets
    alt.data_transformers.disable_max_rows()

    # generating horizontal bar chart
    overview = alt.Chart(df).mark_bar().encode(
        # defining the column to class by
        alt.Y("source_clean:N",
              title="sources"
              ),
        # aggregating the number of tweets per class
        alt.X("count()"),
        tooltip="count()"
    ).properties(width=720)

    return overview


def plot_choro_usa(dataset=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Function to plot a choropleth map of the mean sentiment per US state.

    Args:
        dataset: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        output map: choropleth map of the mean sentiment per US state.
    """
    # calling utility function to create dataframe
    df_choro = create_dataframe_choropleth(dataset)
    # using vega_datasets(data) to get the borders of the states of the US
    states = alt.topo_feature(data.us_10m.url, feature="states")

    # generating choropleth chart
    choro = alt.Chart(df_choro).mark_geoshape().encode(
        color=alt.Color('sentiment',
                        legend=alt.Legend(title="Positivity",
                                          tickCount=5,
                                          tickMinStep=0.5),
                        scale=alt.Scale(
                            scheme='redyellowgreen', domain=[-1, 1])
                        ),
        tooltip=["name:N", "sentiment"]
    ).properties(
        width=720,
        height=400
    )

    # generating chart consisting of the states
    background_usa = alt.Chart(states).mark_geoshape(
        fill="lightgray",
        stroke="white"
    ).properties(
        width=720,
        height=400
    )

    # generating the final layered chart
    output_map = (background_usa + choro).project("albersUsa")

    return output_map


def plot_all(dataset=f"data/{_OUTPUT_JSON_FILENAME}"):
    """
    Function to plot all available maps and charts that interact.

    Available charts and maps:
        plot_stats_world
        plot_tweets_world
        plot_stats_usa
        plot_tweets_usa
        plot_choro_usa

    Args:
        dataset: JSON formatted file with tweet data.
            Defaults to "data/_OUTPUT_JSON_FILENAME".

    Returns:
        output_map: Collection of all maps and charts.
    """
    # calling utility functions to create dataframes
    df_world = create_dataframe_world(dataset)
    df_usa = create_dataframe_us(dataset)
    choro = create_dataframe_choropleth(dataset)

    # using vega_datasets(data)
    countries = alt.topo_feature(data.world_110m.url, feature='countries')
    states = alt.topo_feature(data.us_10m.url, feature="states")
    # using altair function to create a spherical background
    sphere = alt.sphere()

    # setting variables for interaction
    # setting actual selection
    brush = alt.selection_multi(encodings=["y"])
    # setting the opacity of (un)selected bars
    opacity_overview = alt.condition(brush, alt.value(0.9), alt.value(0.1))
    # setting the opacity of (un)selected points
    opacity_points = alt.condition(brush, alt.value(1), alt.value(0))

    # disable the maximum rows restriction to be able to chart larger datasets
    alt.data_transformers.disable_max_rows()

    # spheric background
    spheric_background = alt.Chart(sphere).mark_geoshape(fill="aliceblue")

    # us-states background
    background_usa = alt.Chart(states).mark_geoshape(
        fill="lightgray",
        stroke="white"
    ).properties(
        width=720,
        height=400
    )

    # world countries background
    background_world = alt.Chart(countries).mark_geoshape(
        fill='lightgray',
        stroke='white'
    ).properties(
        width=720,
        height=400
    )

    # plot_tweets_world()
    tweets_world = alt.Chart(df_world).mark_square(size=1, opacity=0.8).encode(
        longitude="coord_lon",
        latitude="coord_lat",
        color=alt.Color("sentiment:N",
                        scale=alt.Scale(
                            domain=["positive", "neutral", 'negative'],
                            range=["green", "orange", "red"]
                        )
                        ),
        tooltip=["user_name", "text", "sentiment"],
        opacity=opacity_points
    ).add_selection(brush)

    # plot_tweets_usa()
    tweets_usa = alt.Chart(df_usa).mark_square(size=5, opacity=0.5).encode(
        longitude="coord_lon",
        latitude="coord_lat",
        color=alt.Color("sentiment:N",
                        scale=alt.Scale(
                            domain=["positive", "neutral", "negative"],
                            range=["green", "orange", "red"]
                        )
                        ),
        tooltip=["user_name", "text", "sentiment"],
        opacity=opacity_points
    ).add_selection(brush)

    # plot_stats_world()
    stats_world = alt.Chart(df_world).mark_bar().encode(
        alt.Y("source_clean:N",
              title="sources"
              ),
        alt.X("count()"),
        opacity=opacity_overview,
        tooltip="count()"
    ).add_selection(brush).properties(width=720).interactive()

    # plot_stats_usa()
    stats_usa = alt.Chart(df_usa).mark_bar().encode(
        alt.Y("source_clean:N",
              title="sources"
              ),
        alt.X("count()"),
        opacity=opacity_overview,
        tooltip="count()"
    ).add_selection(brush).properties(width=720).interactive()

    # plot_choro_usa()
    choro = alt.Chart(choro).mark_geoshape().encode(
        color=alt.Color('sentiment',
                        legend=alt.Legend(title="Positivity",
                                          tickCount=5,
                                          tickMinStep=0.5),
                        scale=alt.Scale(
                            scheme='redyellowgreen', domain=[-1, 1])
                        ),
        tooltip=["name:N", "sentiment"]
    ).properties(
        width=720,
        height=400
    ).add_selection(brush)

    # generating the final layered chart
    output_map = stats_world &\
        (spheric_background + background_world + tweets_world).project(
            "naturalEarth1") &\
        stats_usa &\
        (background_usa + tweets_usa).project("albersUsa") &\
        (background_usa + choro).project("albersUsa")

    return output_map

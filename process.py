# from pyspark import SparkContext
from pyspark.sql import SQLContext
import pandas as pd
import os
import re
import pyspark.sql.functions as func

################################################################################
## register tables
################################################################################
# sc = SparkContext(appName = "movies")
sc.setLogLevel("ERROR")
sqlContext = SQLContext(sc)

filenames = os.listdir('./movie-scores')

## load all json files into dataframes and register as tables
for fn in filenames:
    df = sqlContext.read.json('file:///home/songxh/618-projectA/movie-scores/' + fn)
    if fn == 'movies.json':
        # remove years with less than 10 movies and duplicated ids
        df = df.filter(df.year >= 1930).filter(df.year < 2010)
    tbname = fn.replace('movie_', '')[:-5]
    df.registerTempTable(tbname)

## Table names: movies, tags, locations, genres, directors, countries, actors, tags_map, user_ratings

## Columns of interests:
## movies: id, title, year, rtAllCriticsRating, rtAllCriticsNumReviews, rtAllCriticsNumFresh, rtAllCriticsNumRotten, rtAllCriticsScore, rtTopCriticsRating,
##         rtTopCriticsNumReviews, rtTopCriticsNumFresh, rtTopCriticsNumRotten, rtTopCriticsScore, rtAudienceRating, rtAudienceNumRatings, rtAudienceScore
## movie_countries: movieID, country (not very important)
## movie_genres: movieID, genre
## movie_actors: movieID, actorID, actorName, ranking
## movie_directors: movieID, directorID, directorName
## movie_locations: movieID, location1, location2, location3, location4 (least important one)
## movie_tags: movieID, tagID, tagWeight
## tags_map: id, value
## user_ratings: userID, movieID, rating


################################################################################
## Tasks
################################################################################
# 1.Trend over time
sql_years = """
SELECT year, COUNT(imdbID) AS count
  FROM movies
  GROUP BY year
  ORDER BY year
"""
years = sqlContext.sql(sql_years)
years.toPandas().to_csv('output/years.tsv', sep = '\t', index = False)

sql_trends = """
SELECT year, AVG(rtAllCriticsRating) AS rtAllCritRating, AVG(rtTopCriticsRating) AS rtTopCritRating,
       AVG(rtAllCriticsScore) AS rtAllCritScore, AVG(rtTopCriticsScore) AS rtTopCritScore,
       AVG(rtAudienceRating) AS rtAudRating, AVG(rtAudienceScore) AS rtAudScore,
       AVG(imdbRating) AS imdbRating, AVG(Metascore) AS Metascore, COUNT(id) AS count
  FROM movies
  GROUP BY year
  ORDER BY year
"""
trends = sqlContext.sql(sql_trends)
trends.toPandas().to_csv('output/trends.tsv', sep = '\t', index = False)

# score distribution of each genre
sql_genre = """
SELECT m.id, m.year, m.rtAllCriticsScore, m.rtAudienceScore, m.imdbRating, m.Metascore, g.genre
  FROM movies AS m JOIN genres AS g ON m.id = g.movieID
"""
genres = sqlContext.sql(sql_genre)
genres.toPandas().to_csv('output/genres.tsv', sep = '\t', index = False)

# 2.actors/directors with highest average scores, 3 movies or more
# can also look at the actor/director duos, like Johnny Depp and Tim Burton
sql_meta = """
SELECT md.directorName, AVG(m.Metascore) AS Metascore, COUNT(m.id) AS count
  FROM movies AS m JOIN directors AS md ON m.id = md.movieID
  WHERE m.Metascore != 'N/A'
  GROUP BY md.directorName
  HAVING COUNT(m.id) >= 3
  ORDER BY Metascore DESC
"""
topD_meta = sqlContext.sql(sql_meta).collect()

sql_imdb = """
SELECT md.directorName, AVG(m.imdbRating) AS imdbRating, COUNT(m.id) AS count
  FROM movies AS m JOIN directors AS md ON m.id = md.movieID
  WHERE m.imdbRating != 'N/A'
  GROUP BY md.directorName
  HAVING COUNT(m.id) >= 3
  ORDER BY imdbRating DESC
"""
topD_imdb = sqlContext.sql(sql_imdb).collect()

sql_tomato = """
SELECT md.directorName, AVG(m.rtAllCriticsScore) AS Tomatometer, COUNT(m.id) AS count
  FROM movies AS m JOIN directors AS md ON m.id = md.movieID
  WHERE m.rtAllCriticsNumReviews != 0
  GROUP BY md.directorName
  HAVING COUNT(m.id) >= 3
  ORDER BY Tomatometer DESC
"""
topD_tomato = sqlContext.sql(sql_tomato).collect()

sql_rtAud = """
SELECT md.directorName, AVG(m.rtAudienceScore) AS rtAudScore, COUNT(m.id) AS count
  FROM movies AS m JOIN directors AS md ON m.id = md.movieID
  WHERE m.rtAudienceNumRatings != 0
  GROUP BY md.directorName
  HAVING COUNT(m.id) >= 3
  ORDER BY rtAudScore DESC
"""
topD_rtAud = sqlContext.sql(sql_rtAud).collect()

# actor/director duos
sql_duo_base = """
SELECT *
    FROM movies AS m JOIN actors AS ma ON m.id = ma.movieID
      JOIN directors AS md ON m.id = md.movieID
    WHERE ma.ranking <= 10
"""
duo_base = sqlContext.sql(sql_duo_base)
duo_base.registerTempTable('duo_base')

# metascore
sql_duo_meta = """
SELECT FIRST(directorName) AS directorName, FIRST(actorName) AS actorName,
       AVG(Metascore) AS Metascore, COUNT(imdbID) AS count
  FROM duo_base
  WHERE Metascore != 'N/A'
  GROUP BY directorID, actorID
  HAVING count >= 3
  ORDER BY Metascore DESC
"""
duo_meta = sqlContext.sql(sql_duo_meta)
duo_meta.toPandas().to_csv('output/duo_meta.tsv', sep = '\t', index = False, encoding = 'latin1')

# imdb
sql_duo_imdb = """
SELECT FIRST(directorName) AS directorName, FIRST(actorName) AS actorName,
       AVG(imdbRating) AS imdbRating, COUNT(imdbID) AS count
  FROM duo_base
  WHERE imdbRating != 'N/A'
  GROUP BY directorID, actorID
  HAVING count >= 3
  ORDER BY imdbRating DESC
"""
duo_imdb = sqlContext.sql(sql_duo_imdb)
duo_imdb.toPandas().to_csv('output/duo_imdb.tsv', sep = '\t', index = False, encoding = 'latin1')

# tomatometer
sql_duo_tomato = """
SELECT FIRST(directorName) AS directorName, FIRST(actorName) AS actorName,
       AVG(rtAllCriticsScore) AS Tomatometer, COUNT(imdbID) AS count
  FROM duo_base
  WHERE rtAllCriticsNumReviews > 0
  GROUP BY directorID, actorID
  HAVING count >= 3
  ORDER BY Tomatometer DESC
"""
duo_tomato = sqlContext.sql(sql_duo_tomato)
duo_tomato.toPandas().to_csv('output/duo_tomato.tsv', sep = '\t', index = False, encoding = 'latin1')

# rt audience 
sql_duo_rtaud = """
SELECT FIRST(directorName) AS directorName, FIRST(actorName) AS actorName,
       AVG(rtAudienceScore) AS rtAudScore, COUNT(imdbID) AS count
  FROM duo_base
  WHERE rtAudienceNumRatings > 0
  GROUP BY directorID, actorID
  HAVING count >= 3
  ORDER BY rtAudScore DESC
"""
duo_rtaud = sqlContext.sql(sql_duo_rtaud)
duo_rtaud.toPandas().to_csv('output/duo_rtaud.tsv', sep = '\t', index = False, encoding = 'latin1')

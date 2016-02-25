#!/usr/bin/python
from glob import glob
import numpy
import pickle
import pandas
import json
import sys
import os

base = sys.argv[1]
results = "%s/results" %(base)
scores_folder = "%s/classification" %(base)
scores = glob("%s/*.pkl" %scores_folder)

# Let's save a big data frame of the prediction scores
comparison_df = pandas.DataFrame(columns=["actual","predicted","cca_score"])

total = 0
correct = 0
for i in range(0,len(scores)):
    print "Parsing score %s of %s" %(i,len(scores))
    single_result = pickle.load(open(scores[i],"rb"))
    total=total+2
    correct=correct+single_result["number_correct"]
    comparison_df = comparison_df.append(single_result["comparison_df"])

# Use file names for index
index_names = []
for score in scores:
    fname = os.path.basename(score)
    index_names = index_names + [fname,fname,fname,fname]

comparison_df.index = index_names
accuracy = correct/float(total)
result = dict()
result["comparison_df"] = comparison_df
result["total"] = total
result["correct"] = correct
result["accuracy"] = accuracy
pickle.dump(result,open("%s/classification_results_binary_4mm.tsv" %results,"wb"))

# Create a confusion matrix
binary = pickle.load(open("%s/classification_results_binary_4mm.tsv" %results,"rb"))
binary_df = binary["comparison_df"]

unique_images = [int(x) for x in binary_df.actual.unique().tolist()]
confusion = pandas.DataFrame(0,index=unique_images,columns=unique_images)

# We cannot evaluate images with NaN - meaning the predicted image vector was empty
nanimages = []

print "Generating confusion matrix..."
for i in range(0,len(scores)):
    print "Parsing confusion matrix for %s of %s" %(i,len(scores))
    single_result = pickle.load(open(scores[i],"rb"))    
    cdf = single_result["comparison_df"]
    actuals = cdf.actual.unique().tolist()
    cdf.index = cdf.predicted.tolist()
    if cdf["cca_score"].isnull().any():
        predicted_nulls = cdf["predicted"][cdf["cca_score"].isnull()].unique()
        for predicted_null in predicted_nulls:
            if predicted_null not in nanimages:
                nanimages.append(predicted_null)
    else:
        for actual in actuals:
            predictions = cdf.cca_score[cdf.actual==actual]
            predictions.sort_values(ascending=False,inplace=True)
            predicted = int(predictions.index[0])
            actual = int(actual)  
            confusion.loc[actual,predicted] = confusion.loc[actual,predicted] + 1

#nanimages
# [8718.0, 2963.0, 8727.0, 116.0, 111.0]

# Remove images that are not comparable
for nanimage in nanimages:
    confusion = confusion.drop(nanimage,axis=0)
    confusion = confusion.drop(nanimage,axis=1)

#88 left

confusion.to_csv("%s/classification_confusion_binary_4mm.tsv" %results,sep="\t")
# Normalize confusion 
confusion = confusion.divide(confusion.sum(1).tolist())
confusion.to_csv("%s/classification_confusion_binary_4mm_norm.tsv" %results,sep="\t")

# We also want to output a format for a visualization
# var data = [
#  {
#    z: [[1, 20, 30, 50, 1], [20, 1, 60, 80, 30], [30, 60, 1, -10, 20]],
#    x: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
#    y: ['Morning', 'Afternoon', 'Evening'],
#    type: 'heatmap'
#  }
# ];

# Use image contrast names
images = pandas.read_csv("%s/contrast_defined_images_filtered.tsv" %results,encoding="utf-8",sep="\t")
names = images.cognitive_contrast_cogatlas[images.image_id.isin(unique_images)].tolist()

data = {"type":"heatmap"}
data["x"] = names
data["y"] = names
z = []
for row in confusion.iterrows():
    z.append(row[1].tolist())


data["z"] = z
data = [data]
filey = open("%s/classification_confusion_binary_4mm.json" %results,'wb')
filey.write(json.dumps(data, sort_keys=True,indent=4, separators=(',', ': ')))
filey.close()


# Finally, let's generate a RIGHT/WRONG by concepts data frame, to see how often different concepts are associated with correct or incorrect prediction
concepts_df = pandas.DataFrame(0,columns=["correct","incorrect","number_images"],index=concepts)
confusion = pandas.read_csv("%s/classification_confusion_binary_4mm.tsv" %results,sep="\t",index_col=0)

# Read in concept labels
labels_tsv = "%s/images_contrasts_df.tsv" %results
labels = pandas.read_csv(labels_tsv,sep="\t",index_col=0)

for row in confusion.iterrows():
    actual = str(row[0])
    actual_concepts = labels.loc[int(actual)][labels.loc[int(actual)]==1].index.tolist()
    predictions = row[1]
    for predicted,predicted_count in predictions.iteritems():
        if predicted == actual:
            concepts_df.loc[actual_concepts,"correct"] = concepts_df.loc[actual_concepts,"correct"] + predicted_count
        else:
            concepts_df.loc[actual_concepts,"incorrect"] = concepts_df.loc[actual_concepts,"incorrect"] + predicted_count
        concepts_df.loc[actual_concepts,"number_images"] = concepts_df.loc[actual_concepts,"number_images"] + 1

concepts_df.to_csv("%s/classification_concept_confusion_cogatid.tsv" %results,sep="\t")

# Replace concept ids with concept names
conceptnames = []
for conceptname in concepts_df.index:
    conceptnames.append(get_concept(id=conceptname).json[0]["name"])

concepts_df.index = conceptnames        
concepts_df.to_csv("%s/classification_concept_confusion.tsv" %results,sep="\t")

# Finally, normalize by the row count (to see what percentage of the time we get it wrong/right)
concepts_df_norm = pandas.DataFrame(columns=["correct","incorrect","number_images"])
for row in concepts_df.iterrows():
   rowsum = row[1].sum()
   if rowsum != 0:
       concepts_df_norm.loc[row[0]] = [float(x)/rowsum for x in row[1].tolist()[0:2]] + [concepts_df.loc[row[0],"number_images"]]

concepts_df_norm = concepts_df_norm.sort(columns=["correct"],ascending=False)
concepts_df_norm.to_csv("%s/classification_concept_confusion_norm.tsv" %results,sep="\t")

# Compile null
scores_folder = "%s/classification_null" %(base)
scores = glob("%s/*.pkl" %scores_folder)

comparison_null = []

# Missing images expression to search for
missing_expression = "|".join([str(int(x)) for x in nanimages])

for i in range(0,len(scores)):
    print "Parsing score %s of %s" %(i,len(scores))
    if not re.search(missing_expression,scores[i]):
        single_result = pickle.load(open(scores[i],"rb"))
        comparison_null.append(single_result["accuracy"])
    else:
        print "Skipping %s" %(scores[i])

accuracy = numpy.mean(comparison_null)
result = dict()
result["comparison_null"] = comparison_null
result["accuracy"] = accuracy
pickle.dump(result,open("%s/classification_results_null_4mm.pkl" %results,"wb"))

#>>> result["accuracy"]
#0.46994355374921259

# Do two sample T test against actual vs null accuracies
result_weighted = pickle.load(open("%s/classification_results_weighted_4mm.pkl" %results,"rb"))
result_binary = pickle.load(open("%s/classification_results_binary_4mm.tsv" %results,"rb"))
from scipy.stats import ttest_1samp
tstat_weighted,pval_weighted = ttest_1samp(comparison_null,result_weighted["accuracy"])
tstat_binary,pval_binary = ttest_1samp(comparison_null,result_binary["accuracy"])

# Add to saved results
result_weighted["tstat"] = tstat_weighted
#(-935.83608953817543, 0.0)
result_weighted["pval"] = pval_weighted
# weighted not the appropriate null distribution, but tested anyway
result_binary["tstat"] = tstat_binary
result_binary["pval"] = pval_binary
# (-940.15479080240027, 0.0)

pickle.dump(result_binary,open("%s/classification_results_binary_4mm.pkl" %results,"wb"))
pickle.dump(result_weighted,open("%s/classification_results_weighted_4mm.pkl" %results,"wb"))


# Redo the classification results with these images removed
scores_folder = "%s/classification" %(base)
scores = glob("%s/*.pkl" %scores_folder)

# Let's save a big data frame of the prediction scores
comparison_df = pandas.DataFrame(columns=["actual","predicted","cca_score"])

total = 0
correct = 0
for i in range(0,len(scores)):
    print "Parsing score %s of %s" %(i,len(scores))
    if not re.search(missing_expression,scores[i]):
        single_result = pickle.load(open(scores[i],"rb"))
        total=total+2
        correct=correct+single_result["number_correct"]
        comparison_df = comparison_df.append(single_result["comparison_df"])
    else:
        print "Skipping %s" %(scores[i])

# Use file names for index
index_names = []
for score in scores:
    if not re.search(missing_expression,score):
        fname = os.path.basename(score)
        index_names = index_names + [fname,fname,fname,fname]

comparison_df.index = index_names
accuracy = correct/float(total)
result = dict()
result["comparison_df"] = comparison_df
result["total"] = total
result["correct"] = correct
result["accuracy"] = accuracy
pickle.dump(result,open("%s/classification_results_binary_4mm.tsv" %results,"wb"))
#>>> accuracy
#0.81429691583899633

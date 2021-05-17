#!/usr/bin/env nextflow
nextflow.enable.dsl=2



process TSV_SORT_BY_COLUMN {

  input:
    stdin
    val column_index
  
  output:
    path 'bro'
  """
    sort -k${column_index} -r -n > bro

  """
}


process TSV_REMOVE_SAME_COLUMN {

  input:
    path x
    val col1 
    val col2
  
  output:
    stdout
  """
    awk -F"\t" '\$${col1}!=\$${col2}' $x
  """

}


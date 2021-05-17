#!/usr/bin/env nextflow
nextflow.enable.dsl=2


params.block_size = 10
params.extra_diamond_arg_string = ''

process DIAMOND_MAKEDB {
  cpus = 1
  
  input:
    path x
    val out_name //output file name
  
  output:
    path "${out_name}.dmnd"
  """
  diamond makedb --in ${x} --db ${out_name} -p ${task.cpus}

  """

}

process DIAMOND_BLASTP {
  label 'process_high'
  label 'process_long'
  tag "diamond blastp on ${query_path} vs ${db_path} "
  input:
    path query_path 
    path db_path
    val out_name //output file name
  
  output:
    path "${out_name}.blastp.tsv"
  """
   diamond blastp \
    --query ${query_path} \
    --db ${db_path} \
    --threads ${task.cpus} \
    --outfmt 6 \
    --out ${out_name}.blastp.tsv \
    ${params.extra_diamond_arg_string} \
    -b ${params.block_size} 

  """

}



process REMOVE_EXTRA {

  input:
    path x
  
  output:
    path "out.faa"
  """
  sed "s/ #.*\$//" ${x} > out.faa

  """

}



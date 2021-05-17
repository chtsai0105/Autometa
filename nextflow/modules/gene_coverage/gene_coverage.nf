#!/usr/bin/env nextflow
nextflow.enable.dsl=2


params.orf_fasta_path = null

include { REMOVE_EXTRA; DIAMOND_MAKEDB; DIAMOND_BLASTP } from './process/diamond.nf' addParams(extra_diamond_arg_string: '--no-self-hits')
include { TSV_SORT_BY_COLUMN; TSV_REMOVE_SAME_COLUMN } from './process/utilities.nf' 


workflow PAIRWISE_BLAST {

    take:
        orfs

    main:
        REMOVE_EXTRA(orfs)
        DIAMOND_MAKEDB(REMOVE_EXTRA.out, "allvsall")
        DIAMOND_BLASTP(REMOVE_EXTRA.out, DIAMOND_MAKEDB.out, "yep")
        TSV_REMOVE_SAME_COLUMN(DIAMOND_BLASTP.out, 1, 2)
        TSV_SORT_BY_COLUMN(TSV_REMOVE_SAME_COLUMN.out, 3)
}


workflow {
    main:
        orfs = Channel.fromPath("${params.orf_fasta_path}")
        GENE_COVERAGE(orfs)
}
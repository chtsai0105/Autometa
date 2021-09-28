#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COPYRIGHT
Copyright 2021 Ian J. Miller, Evan R. Rees, Kyle Wolf, Siddharth Uppal,
Shaurya Chanana, Izaak Miller, Jason C. Kwan

This file is part of Autometa.

Autometa is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Autometa is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Autometa. If not, see <http://www.gnu.org/licenses/>.
COPYRIGHT

Script to summarize Autometa binning results
"""

import logging
import os

import pandas as pd
import numpy as np

from Bio import SeqIO

from autometa.taxonomy.ncbi import NCBI
from autometa.taxonomy import majority_vote
from autometa.common import markers


logger = logging.getLogger(__name__)


def write_cluster_records(
    bin_df: pd.DataFrame, metagenome: str, outdir: str, cluster_col: str = "cluster"
) -> None:
    """Write clusters to `outdir` given clusters `df` and metagenome `records`

    Parameters
    ----------
    bin_df : pd.DataFrame
        Autometa binning dataframe. index='contig', cols=['cluster', ...]
    metagenome : str
        Path to metagenome fasta file
    outdir : str
        Path to output directory to write fastas for each metagenome-assembled genome
    cluster_col : str, optional
        Clustering column by which to group metabins

    """
    if os.path.isdir(outdir):
        raise ValueError(
            f"{outdir} already exists! Please provide a path to a non-existent directory path"
        )
    os.makedirs(outdir)
    mgrecords = [rec for rec in SeqIO.parse(metagenome, "fasta")]
    for cluster, dff in bin_df.fillna(value={cluster_col: "unclustered"}).groupby(
        cluster_col
    ):
        contigs = set(dff.index)
        records = [rec for rec in mgrecords if rec.id in contigs]
        outfpath = os.path.join(outdir, f"{cluster}.fna")
        SeqIO.write(records, outfpath, "fasta")
    return


def fragmentation_metric(df: pd.DataFrame, quality_measure: float = 0.50) -> int:
    """Describes the quality of assembled genomes that are fragmented in
    contigs of different length.

    Note
    ----

        For more information see this metagenomics `wiki <http://www.metagenomics.wiki/pdf/definition/assembly/n50>`_ from Matthias Scholz

    Parameters
    ----------
    df: pd.DataFrame
        DataFrame to assess fragmentation within metagenome-assembled genome.
    quality_measure : 0 < float < 1
        Description of parameter `quality_measure` (the default is .50).
        I.e. default measure is N50, but could use .1 for N10 or .9 for N90

    Returns
    -------
    int
        Minimum contig length to cover `quality_measure` of genome (i.e. percentile contig length)

    """
    target_size = df.length.sum() * quality_measure
    lengths = 0
    for length in df.length.sort_values(ascending=False):
        lengths += length
        if lengths >= target_size:
            return length


def get_metabin_stats(
    bin_df: pd.DataFrame, markers_fpath: str, cluster_col: str = "cluster"
) -> pd.DataFrame:
    """Retrieve statistics for all clusters recovered from Autometa binning.

    Parameters
    ----------
    bin_df : pd.DataFrame
        Autometa binning table. index=contig, cols=['cluster','length', 'GC', 'coverage', ...]
    markers_fpath : str
        Path to autometa annotated and filtered markers table respective to kingdom binned.
    cluster_col : str, optional
        Clustering column by which to group metabins

    Returns
    -------
    pd.DataFrame
        dataframe consisting of various metagenome-assembled genome statistics indexed by cluster.
    """
    logger.info(f"Retrieving metabins' stats for {cluster_col}")
    stats = []
    markers_df = markers.load(markers_fpath)
    for cluster, dff in bin_df.fillna(value={cluster_col: "unclustered"}).groupby(
        cluster_col
    ):
        length_weighted_coverage = np.average(
            a=dff.coverage, weights=dff.length / dff.length.sum()
        )
        length_weighted_gc = np.average(
            a=dff.gc_content, weights=dff.length / dff.length.sum()
        )
        num_expected_markers = markers_df.shape[1]
        cluster_pfams = markers_df[markers_df.index.isin(dff.index)]
        if cluster_pfams.empty:
            total_markers = 0
            num_single_copy_markers = 0
            num_markers_present = 0
            completeness = pd.NA
            purity = pd.NA
        else:
            pfam_counts = cluster_pfams.sum()
            total_markers = pfam_counts.sum()
            num_single_copy_markers = pfam_counts[pfam_counts == 1].count()
            num_markers_present = pfam_counts[pfam_counts >= 1].count()
            completeness = num_markers_present / num_expected_markers * 100
            purity = num_single_copy_markers / num_markers_present * 100

        stats.append(
            {
                cluster_col: cluster,
                "nseqs": dff.shape[0],
                "seqs_pct": dff.shape[0] / bin_df.shape[0] * 100,
                "size (bp)": dff.length.sum(),
                "size_pct": dff.length.sum() / bin_df.length.sum() * 100,
                "N90": fragmentation_metric(dff, quality_measure=0.9),
                "N50": fragmentation_metric(dff, quality_measure=0.5),
                "N10": fragmentation_metric(dff, quality_measure=0.1),
                "length_weighted_gc_content": length_weighted_gc,
                "min_gc_content": dff.gc_content.min(),
                "max_gc_content": dff.gc_content.max(),
                "std_gc_content": dff.gc_content.std(),
                "length_weighted_coverage": length_weighted_coverage,
                "min_coverage": dff.coverage.min(),
                "max_coverage": dff.coverage.max(),
                "std_coverage": dff.coverage.std(),
                "completeness": completeness,
                "purity": purity,
                "num_total_markers": total_markers,
                f"num_unique_markers (expected {num_expected_markers})": num_markers_present,
                "num_single_copy_markers": num_single_copy_markers,
            }
        )
    return pd.DataFrame(stats).set_index(cluster_col).convert_dtypes()


def get_metabin_taxonomies(
    bin_df: pd.DataFrame, ncbi: NCBI, cluster_col: str = "cluster"
) -> pd.DataFrame:
    """Retrieve taxonomies of all clusters recovered from Autometa binning.

    Parameters
    ----------
    bin_df : pd.DataFrame
        Autometa binning table. index=contig, cols=['cluster','length','taxid', *canonical_ranks]
    ncbi : autometa.taxonomy.ncbi.NCBI instance
        Autometa NCBI class instance
    cluster_col : str, optional
        Clustering column by which to group metabins

    Returns
    -------
    pd.DataFrame
        Dataframe consisting of cluster taxonomy with taxid and canonical rank.
        Indexed by cluster
    """
    logger.info(f"Retrieving metabin taxonomies for {cluster_col}")
    canonical_ranks = [rank for rank in NCBI.CANONICAL_RANKS if rank != "root"]
    is_clustered = bin_df[cluster_col].notnull()
    bin_df = bin_df[is_clustered]
    outcols = [cluster_col, "length", "taxid", *canonical_ranks]
    tmp_lines = (
        bin_df[outcols]
        .to_csv(sep="\t", index=False, header=False, line_terminator="\n")
        .split("\n")
    )
    taxonomies = {}
    # Here we prepare our datastructure for the majority_vote.rank_taxids(...) function.
    for line in tmp_lines:
        if not line:
            # Account for end of file where we have empty string.
            continue
        llist = line.strip().split("\t")
        cluster = llist[0]
        length = int(llist[1])
        taxid = int(llist[2])
        ranks = llist[3:]
        for rank, canonical_rank in zip(ranks, canonical_ranks):
            if rank != "unclassified":
                break
        if cluster not in taxonomies:
            taxonomies.update({cluster: {canonical_rank: {taxid: length}}})
        elif canonical_rank not in taxonomies[cluster]:
            taxonomies[cluster].update({canonical_rank: {taxid: length}})
        elif taxid not in taxonomies[cluster][canonical_rank]:
            taxonomies[cluster][canonical_rank].update({taxid: length})
        else:
            taxonomies[cluster][canonical_rank][taxid] += length
    cluster_taxonomies = majority_vote.rank_taxids(taxonomies, ncbi)
    # With our cluster taxonomies, let's place these into a dataframe for easy data accession
    cluster_taxa_df = pd.Series(data=cluster_taxonomies, name="taxid").to_frame()
    # With the list of taxids, we'll retrieve their complete canonical-rank information
    lineage_df = ncbi.get_lineage_dataframe(cluster_taxa_df.taxid.tolist(), fillna=True)
    # Now put it all together
    cluster_taxa_df = pd.merge(
        cluster_taxa_df, lineage_df, how="left", left_on="taxid", right_index=True
    )
    cluster_taxa_df.index.name = cluster_col
    return cluster_taxa_df


def main():
    import argparse
    import logging as logger

    logger.basicConfig(
        format="[%(asctime)s %(levelname)s] %(name)s: %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
        level=logger.DEBUG,
    )
    parser = argparse.ArgumentParser(
        description="Summarize Autometa results writing genome fastas and their respective"
        " taxonomies/assembly metrics for respective metagenomes",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--binning-main",
        help="Path to Autometa binning main table (output from --binning-main argument)",
        metavar="filepath",
        required=True,
    )
    parser.add_argument(
        "--markers",
        help="Path to annotated markers respective to domain (bacteria or archaea) binned",
        metavar="filepath",
        required=True,
    )
    parser.add_argument(
        "--metagenome",
        help="Path to metagenome assembly",
        metavar="filepath",
        required=True,
    )
    parser.add_argument(
        "--ncbi",
        help="Path to user NCBI databases directory (Required for retrieving metabin taxonomies)",
        metavar="dirpath",
        required=False,
    )
    parser.add_argument(
        "--binning-column",
        help="Binning column to use for grouping metabins",
        metavar="str",
        required=False,
        default="cluster",
    )
    parser.add_argument(
        "--output-stats",
        help="Path to write metabins stats table",
        metavar="filepath",
        required=True,
    )
    parser.add_argument(
        "--output-taxonomy",
        help="Path to write metabins taxonomies table",
        metavar="filepath",
        required=True,
    )
    parser.add_argument(
        "--output-metabins",
        help="Path to output directory. (Directory must not exist. This directory will be created.)",
        metavar="dirpath",
        required=True,
    )
    args = parser.parse_args()

    bin_df = pd.read_csv(args.binning_main, sep="\t", index_col="contig")
    if bin_df.empty:
        logger.error(f"{args.binning} empty...")
        exit(1)

    # First write out directory with fasta files per each metabin
    write_cluster_records(
        bin_df=bin_df,
        metagenome=args.metagenome,
        outdir=args.output_metabins,
        cluster_col=args.binning_column,
    )
    # Now retrieve stats for each metabin
    metabin_stats_df = get_metabin_stats(
        bin_df=bin_df,
        markers_fpath=args.markers,
        cluster_col=args.binning_column,
    )
    metabin_stats_df.to_csv(args.output_stats, sep="\t", index=True, header=True)
    logger.info(f"Wrote metabin stats to {args.output_stats}")
    # Finally if taxonomy information is available then write out each metabin's taxonomy by modified majority voting method.
    if "taxid" in bin_df.columns:
        if not args.ncbi:
            logger.warn(
                "taxid found in dataframe. --ncbi argument is required to retrieve metabin taxonomies. Skipping..."
            )
        else:
            ncbi = NCBI(dirpath=args.ncbi)
            taxa_df = get_metabin_taxonomies(
                bin_df=bin_df, ncbi=ncbi, cluster_col=args.binning_column
            )
            taxa_df.to_csv(args.output_taxonomy, sep="\t", index=True, header=True)


if __name__ == "__main__":
    main()
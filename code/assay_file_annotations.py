import collections
import logging

import synapseclient
import synapseutils

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def store_table_and_reindex(syn, tbl, res):
    """Store a Synapse table and then force it to be indexed.

    """
    new_tbl = syn.store(synapseclient.Table(tbl, res))
    logger.debug("Stored table, forcing reindex.")
    _ = syn.tableQuery(f'SELECT id FROM {tbl} LIMIT 1')
    return(new_tbl)


def annotations_for_folder(syn, folder_id, tbl, key, value, dry_run=False):
    """Walk a container and find all folders and apply key=value 
       annotation to all files in them.
    """
    w = synapseutils.walk(syn, folder_id)
    folders = set([x[0][1].lstrip('syn') for x in w])
    q = 'SELECT {} FROM {} WHERE parentId IN ({}) AND {} IS NULL'.format(key, tbl, ",".join(folders), key)
    logger.debug(q)
    res = syn.tableQuery(q).asDataFrame()
    logger.info("{} rows to change for key {}.".format(res.shape[0], key))

    res[key] = value

    if not dry_run and not res.empty:
        new_tbl = store_table_and_reindex(syn, tbl, res)
        return(new_tbl)
    else:
        return(res)

def level_zero_folder(syn, folder_id, tbl, dry_run=False):
    """Assume everything in a Data folder that doesn't have a name like
    'MDD_Level.\\..*' is level 0.
    """
    w = synapseutils.walk(syn, folder_id)
    folders = set([x[0][1].lstrip('syn') for x in w])

    q = "SELECT * FROM {} WHERE (parentId IN ({}) AND (name NOT LIKE 'MDD_%Level_.%') AND (Level is NULL) AND (DataType IS NULL OR DataType <> 'Metadata'))".format(tbl, ",".join(folders))
    logger.debug(q)
    res = syn.tableQuery(q).asDataFrame()
    res['Level'] = 0
    logger.info("{} rows to change for level 0.".format(res.shape[0]))
    if not dry_run  and not res.empty:
        new_tbl = store_table_and_reindex(syn, tbl, res)
              return(new_tbl)
    else:
        return(res)

Assay = collections.namedtuple('Assay', 'id name data_folder metadata_folder')

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry_run", action="store_true", default=False)

    args = parser.parse_args()

    synapseclient.utils.printTransferProgress = lambda *a, **k: None
    syn = synapseclient.login(silent=True)

    file_view_id = 'syn18486863'

    assays = [Assay(id='syn16804155', name='ATACseq', data_folder='syn18352471', 
                    metadata_folder='syn18498014'),
              Assay(id='syn12526172', name='Reverse Phase Protein Array', 
                    data_folder='syn12555334', metadata_folder='syn18497865'),
              Assay(id='syn16816761', name='Cyclic Immunofluorescence', 
                    data_folder='syn18502816', metadata_folder='syn18502817'),
              Assay(id='syn15591874', name='Global Chromatin Profiling', 
                    data_folder='syn18491838', metadata_folder='syn18503456'),
              Assay(id='syn13363381', name='Immunofluorescence', 
                    data_folder='syn18675763', metadata_folder='syn18675271'),
              Assay(id='syn18481227', name='L1000', 
                    data_folder='syn18481229', metadata_folder='syn18502906'),
              Assay(id='syn12550434', name='rnaSeq', 
                    data_folder='syn18491785', metadata_folder='syn18497886')
              ]

    for assay in assays:
        logger.info("Processing assay {}".format(assay))

        folder_obj = syn.get(assay.id)
        assert folder_obj.name == assay.name, 'Name of folder and supplied name are different: {} and {}'.format(folder_obj.name, assay.name)

        metadata_folder_obj = syn.get(assay.metadata_folder)
        assert metadata_folder_obj.name == "Metadata", "Not a metadata folder."
        assert metadata_folder_obj.parentId == assay.id, "The folder {} isn't a child of the assay folder.".format(metadata_folder_obj)

        data_folder_obj = syn.get(assay.data_folder)
        assert data_folder_obj.name == "Data", "{} is not a data folder.".format(data_folder_obj)
        assert data_folder_obj.parentId == assay.id, "The folder {} isn't a child of the assay folder.".format(data_folder_obj)

        # Annotate files in assay sub-folders
        _ = annotations_for_folder(syn, assay.id, file_view_id, 'assay', assay.name, 
                                   dry_run=args.dry_run)
        _ = annotations_for_folder(syn, assay.id, file_view_id, 'CellLine', 'MCF10A',
                                   dry_run=args.dry_run)
        _ = annotations_for_folder(syn, assay.id, file_view_id, 'Study', 'MCF10A Deep Dive',
                                   dry_run=args.dry_run)

        # Annotate data in assay metadata sub-folder
        _ = annotations_for_folder(syn, assay.metadata_folder, file_view_id, 
                                'DataType', 'Metadata', dry_run=args.dry_run)

        # Set level 0 to files in data folders
        _ = level_zero_folder(syn, folder_id=assay.data_folder, tbl="syn18486863",
                                dry_run=args.dry_run)

if __name__ == "__main__":
    main()
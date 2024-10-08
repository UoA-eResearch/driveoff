Based on : [https://github.com/workflowhub-eu/about/tree/master/Workflow-RO-Crate](https://github.com/UoA-eResearch/ro-crate-py/pull/1)

# eResearch Project Archive Crate


* Permalink: `TODO`
* Version: [0.0.1](https://github.com/UoA-eResearch/ro-crate-py/pull/1)
* Test Crate-O [Mode](project_archivecrate_mode.json)
* Preliminary [Terms](https://github.com/JLoveUOA/eres_project_archive-ro-terms/tree/master/eres-project-archive)

<!-- As Encrypted crates differ for how they are constructed in memory as opposed to how they are written on disk a profile crate is provided for each.
* [Profile Crate - In Memory `ro-crate-metadata.json`](TODO)
  - [Profile Crate preview](TODO)
* [Profile Crate - On Disk `ro-crate-metadata.json`](TODO)
  - [Profile Crate preview](TODO)
* [Example RO-Crate - In Memory`ro-crate-metadata.json`](TODO)
  - [Example RO-Crate profile preview](TODO)
* [Example RO-Crate - On Disk `ro-crate-metadata.json`](TODO)
  - [Example RO-Crate profile preview](TODO) -->



_eResearch Project Archive Crate_ is an extension of [_RO-Crate_](https://researchobject.github.io/ro-crate/) for documenting long term archived data in the University of Auckland's eResearch data storage systems on a Research Project Basis.


## Concepts

This section uses terminology from the [RO-Crate 1.1 specification](https://w3id.org/ro/crate/1.1) and [University of Auckland's research data management policy](https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-management-policy-guidance)

## Overview

The _eResearch Project Archive Crate_ profile is used to describe an archived collection of research data associated with a research project in the University of Auckland eResearch Storage system.
The metadata described in this crate SHOULD be at least the minimal set required to determine research data and archiving requirements for this data.

_eResearch Project Archive Crate's_ MUST:

- describe data associated with ONE research project.
- describe only data stored locally with the crate.
- describe data stored within University of Auckland systems.
  - Where at least one researcher responsible for the data is affiliated with The University of Auckland's at the time of the data's creation.
- describe data that is archived and not in active use.

_eResearch Project Archive Crates_ MUST be stored as a valid [BagIT](https://datatracker.ietf.org/doc/html/rfc8493) _Bag_. with the `ro_crate_metadata.json` and all data within the `data\` directory of the _Bag_. https://datatracker.ietf.org/doc/html/rfc8493

_eResearch Project Archive Crates_ SHOULD be stored as a single file archive such as a `.tar` (https://lists.gnu.org/archive/html/info-gnu/2023-07/msg00005.html) or `.zip` containing the _Bag_ which in turns contains all metadata and data.

_eResearch Project Archive Crates_ MUST contain one `Project` describing the research project associated with the archived data.


## Conforms To

The Metadata File Descriptor `conformsTo` MUST be a list that contains at least this profile and the RO-Crate profile `"https://w3id.org/ro/crate/1.1"`.

## Root Data Entity

The `root data entity` (dataset with ("@id": "./")) describes the overall dataset found within the _eResearch Project Archive Crate_ as a whole.

the `root data entity` MUST list the `Project` this data is associated with via the `project` property.

All files and directories that are children of the `root data entity` are considered part of the _eResearch Project Archive Crate_. They MAY be specifically listed using the `hasPart` property on the `root data entity`.

the `root data entity` MUST list the sensitivity classification of the data stored in the _crate_ via the `dataClassification` property as this informs [research data retention](https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-classification) periods.

the `root data entity` MUST list the school or faculty this data belongs to via the `sourceOrganization`. This will be the contact point if a `projectOwner` or `dataOwner` cannot be contacted based on the information provided in `project`.


### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**Root data entity ("@id": "./")**  | conformsTo   | MUST   | Text | A URI for the permalinked version of this document and a URI permalink to the [RO-Crate 1.1 specification](https://w3id.org/ro/crate/1.1) `https://w3id.org/ro/crate/1.1`|
|**Root data entity ("@id": "./")**  | project   | MUST   |Project| The Project associated with this data|
|**Root data entity ("@id": "./")**  | sourceOrganization   | MUST   | Organisation|The school or faculty linked with this research project and point of contact if `projectOwner` is not available|
|**Root data entity ("@id": "./")**  | dataClassification   | MUST   | Text | The classification of the data for [research data retention](https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-classification) and [information security](https://www.protectivesecurity.govt.nz/classification/overview).  MUST be ONE of ["Public", "Internal", "Sensitive", or "Restricted"]. Default "Sensitive".|
|**Root data entity ("@id": "./")**  | name   | MAY   | Text | A name describing this dataset.|
|**Root data entity ("@id": "./")**  | hastPart   | MAY   | Dataset OR Datafile | Child Datasets and Files used to sub-section and further describe this archive.|

## Project

The `Project` describes the majority of the information for the research project associated with the data in the _crate_. It should be used to inform decisions regarding data archiving deletion and access controls to sensitive data.

`Projects` MUST list their unique eResearch Project Database ID as their `@id`.

a `Project` MUST provide ONE owner of this project and _crate_ via `projectOwner`.

Additional people associated with the project MAY be provided via the `dataContact` , `dataOwner` and `member` properties.

If the data stored within the _crate_ originates from a Dropbox or a Research Drive then the ID of that `dropbox` or `researchDrive` SHOULD be provided via their respective fields.

The `endDate` describes the date the project ends, e.g. the end of a PHD project or research grant. [Research data retention](https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-retention) dates may be inferred from this based on data classification this date and other factors (such as if this project was sensitive or relates to registered patients). 

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**Project**  | @id  | MUST   | Text | A unique ID for this project. Use code from eResearch Project Database if possible. e.g. ("@id":"#cer03107")|
|**Project**  | @type  | MUST   | Text | MUST include "Project".|
|**Project**  | projectOwner  | MUST  | Person | The owner of this project and primary contact for data retention. (Usually Primary Investigator)|
|**Project**  | endDate  | MUST  | Date | The date that this project ends. Informs when archived data can be safely deleted (for instance for public data, data may be deleted 6 years after project end date).|
|**Project**  | service  | MAY  | Text | Unique ID's of services associated with this project such as Virtual Machines or storage.|
|**Project**  | division  | MAY  | Text | The division linked with this project. e.g. "CIVENV"|
|**Project**  | dropbox  | MAY  | Text OR URL | The URL or identifier of a Dropbox associated with this project SHOULD be included if a dropbox is present. MUST be included if data archived in this crate originated from said dropbox.|
|**Project**  | description  | SHOULD  | Text | full description of the project.|
|**Project**  | name  | SHOULD  | Text | Title describing the project.|
|**Project**  | identifier  | MAY  | Text OR URL | additional identifiers associated with the project.|
|**Project**  | startDate  | MAY  | Date | The date this project starts.|
|**Project**  | dataOwner  | MAY | Person | Project members who own the data stored within, for example PHD students.|
|**Project**  | dataContact  | MAY  | Person | a contact for ownership of this data.|
|**Project**  | member  | MAY  | Person | Any other person associated with the project.|
|**Project**  | requirements  | MAY  | Text | Free-text requirements for this projects, e.g. "requires human ethics approval".|
|**Project**  | researchDrive  | MAY  | Text | the research storage drive associated with this project and archive crate.

## People

`Person` records in the _crate_ SHOULD provide sufficient information to uniquely identify a person within the University of Auckland system and if possible contact them regarding the data in the _crate_.

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**Person**  | @id  | MUST  | Text | A UPI that uniquely identifies this person in the University Active Directory Lookup. e.g. "pmcg006"|
|**Person**  | email  | SHOULD  | Email | an email address that may be used to contact this person.
|**Person**  | name | MAY  | name | The full name identifying this person.

## Additional Datasets

Additional `Dataset` and `Datafile` objects MAY be listed in the crate for more granular information of research data.

They are still governed by the information provided in the `root data entity` and its associated `Project` and so all data entities MUST be listed via `hasPart` in the `root data entity`.

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**Dataset**  | @id  | MUST  | Relative Directory Path | as per [RO-Crate Specification](https://www.researchobject.org/ro-crate/specification/1.1/data-entities.html): URI Path relative to the RO Crate root, or an absolute URI. The id SHOULD end with `/` |
|**Dataset**  | name  | SHOULD  | Text | A meaningful name to describe this dataset. |
|**File**  | @id  | MUST  | Relative File Path | as per [RO-Crate Specification](https://www.researchobject.org/ro-crate/specification/1.1/data-entities.html): MUST be either a URI Path relative to the RO Crate root, or an absolute URI. |
|**File**   | name  | SHOULD  | Text | A meaningful name to describe this file. |
|**Dataset**   | hastPart   | MAY   | Dataset OR Datafile | Child datasets and datafiles used to sub-section and further describe this archive.|
|**File** OR **Dataset**   | isPartOf  | MAY  | Dataset | The dataset this entity is part of, inverse property of hasPart |

## Delete Actions

When a dataset that a *crate* describes is deleted a `DeleteAction` entity SHOULD be added to the crate to record this with an `actionStatus` as `"CompletedActionStatus"` and an `endTime` of the date the data was deleted.

If deletion of data is scheduled and date of deletion is known in advance (such as due to a data retention policy) a `DeleteAction` MAY be used to describe the scheduled deletion event with an `actionStatus` as `"PotentialActionStatus"` and an `endTime` of the date the data is to be deleted.

The *crate* itself MUST NOT be deleted, and should be kept as a record of the data and when it was deleted.

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**DeleteAction**  | targetCollection  | MUST  | Dataset | The dataset that is the target of this delete action.|
|**DeleteAction**  | actionStatus  | MUST  | ActionStatusType | Status of the deletion of the target dataset.|
|**DeleteAction**  | endTime  | MUST  | DateTime | When the deletion of the data is to occur or has occurred.|

## Example eResearch Project Archive Crate
* [ro-crate-metadata.json](exampleCrate/ro-crate-metadata.json)


```json
{
    "@context": "https://w3id.org/ro/crate/1.1/context",
    "@graph": [
        {
            "@id": "./",
            "@type": "Dataset",
            "conformsTo": [
                "https://uoa-eresearch.github.io/Project-Archive-RoCrate-Profile/"
            ],
            "dataClassification": [
                "Sensitive"
            ],
            "datePublished": "2024-10-03T01:05:33+00:00",
            "hasPart": [
                {
                    "@id": "Vault/pancreatoblastoma/raw/"
                },
                {
                    "@id": "Vault/pancreatoblastoma/bam/"
                },
                {
                    "@id": "Vault/pancreatoblastoma/raw/rna/"
                },
                {
                    "@id": "Vault/pancreatoblastoma/raw/rna/1806KHP-0132/A0006L_1.fastq.gz"
                }
            ],
            "name": [
                "Example Project Archive Crate"
            ],
            "project": [
                {
                    "@id": "#cer01502"
                }
            ],
            "sourceOrganization": [
                {
                    "@id": "#UOA_FMHS"
                }
            ]
        },
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {
                "@id": "./"
            },
            "conformsTo": {
                "@id": "https://w3id.org/ro/crate/1.1"
            }
        },
        {
            "@id": "Vault/pancreatoblastoma/bam/",
            "@type": "Dataset"
        },
        {
            "@id": "Vault/pancreatoblastoma/raw/rna/",
            "@type": "Dataset"
        },
        {
            "@id": "Vault/pancreatoblastoma/raw/rna/1806KHP-0132/A0006L_1.fastq.gz",
            "@type": "File"
        },
        {
            "@id": "#jcar001",
            "@type": "Person",
            "email": "JCarberry@psychoceramics.brown.com",
            "identifier": "https://orcid.org/0000-0001-7760-1240",
            "name": "Josiah Carberry"
        },
        {
            "@id": "#tmon023",
            "@type": "Person",
            "email": "TeamMember1@psychoceramics.brown.com",
            "name": "TeamMember1"
        },
        {
            "@id": "#tmtw023",
            "@type": "Person",
            "email": "TeamMember2@psychoceramics.brown.com",
            "name": "TeamMember2"
        },
        {
            "@id": "#UOA_FMHS",
            "@type": "Organization",
            "name": "University Of Auckland Faculty of Medical and Health Science"
        },
        {
            "@id": "#cer01502",
            "@type": "Project",
            "dataContact": [
                {
                    "@id": "#tmon023"
                },
                {
                    "@id": "#tmtw023"
                }
            ],
            "dataOwner": [
                {
                    "@id": "#tmon023"
                },
                {
                    "@id": "#tmtw023"
                }
            ],
            "description": "This storage will be used to keep the Polaris image data and bioinformatics analysis data. Vectra Polaris is a pathology imaging system that provides researchers unparalleled speed, performance, and versatility for extracting proteomic and morphometric information from tissue sections. Using the Polaris and bioinformatics/computational approaches, we will explore multiple biomarkers and functional cellular interactions in spatial context.",
            "division": "CIVENV",
            "dropbox": "virtualeyes-lab",
            "endDate": "2024-10-02",
            "identifier": [
                "ressci202100031",
                "1507"
            ],
            "member": [
                {
                    "@id": "#jcar001"
                },
                {
                    "@id": "#tmon023"
                },
                {
                    "@id": "#tmtw023"
                }
            ],
            "name": "Bioinfceramics",
            "projectOwner": [
                {
                    "@id": "#jcar001"
                }
            ],
            "requirements": "Part of a funded project research,Requires human ethics research",
            "researchDrive": "ressci202100031-polaris-bioinformatics",
            "service": [
                "cbarpuptst01",
                "sc-cer00466-2"
            ],
            "startDate": "2024-10-02"
        },
        {
            "@id": "#DeleteArchiveAction",
            "@type": "DeleteAction",
            "actionStatus": "PotentialActionStatus",
            "endTime": "2024-10-02",
            "targetCollection": [
                {
                    "@id": "./"
                }
            ]
        }
    ]
}

```

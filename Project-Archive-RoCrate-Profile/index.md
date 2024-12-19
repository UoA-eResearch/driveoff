Based on : [https://github.com/workflowhub-eu/about/tree/master/Workflow-RO-Crate](https://github.com/UoA-eResearch/ro-crate-py/pull/1)

# eResearch Project Archive Crate


* Permalink: `TODO`
* Version: [0.0.1](https://github.com/UoA-eResearch/ro-crate-py/pull/1)
* Test Crate-O [Mode](project_archivecrate_mode.json)
* Preliminary [Terms](https://github.com/JLoveUOA/eres_project_archive-ro-terms/tree/master/eres-project-archive)


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

_eResearch Project Archive Crates_ SHOULD be stored as a single file archive such as a `.tar` (https://lists.gnu.org/archive/html/info-gnu/2023-07/msg00005.html) or `.zip` containing the _Bag_ which in turns contains all metadata and data. `.zip` archives will be used as default.

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
|**Root data entity ("@id": "./")**  |  mainEntity  | MUST   |Project OR ResearchDriveService | The Project or storage drive associated with this data|
|**Root data entity ("@id": "./")**  | hastPart   | MAY   | Dataset OR Datafile | Child Datasets and Files used to sub-section and further describe this archive.|

## Project

The `Project` describes the majority of the information for the research project associated with the data in the _crate_. It should be used to inform decisions regarding data archiving deletion and access controls to sensitive data.

`Projects` MUST list their unique eResearch Project Database ID as their `@id`.

a `Project` MUST provide ONE owner of this project and _crate_ via `members` using an `OrganizationRole` with name `Project Owner`.

Additional people associated with the project MAY be provided via the  `member` property as `OrganizationRole`s.

If the data stored within the _crate_ originates from a Dropbox or a Research Drive then the ID of that `dropbox` or `ResearchDriveService` MUST be provided via 'services'

The `endDate` describes the date the project ends, e.g. the end of a PHD project or research grant. [Research data retention](https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-retention) dates may be inferred from this based on data classification this date and other factors (such as if this project was sensitive or relates to registered patients). 

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**Project**  | @id  | MUST   | Text | A unique ID for this project. Use id from eResearch Project Database if possible. e.g. ("@id":"#project/100")|
|**Project**  | @type  | MUST   | Text | MUST include "Project" OR "ResearchProject".|
|**Project**  | member  | MUST  | OrganizationRole | Members with access to this project and its associated services |
|**Project**  | endDate  | MUST  | Date | The date that this project ends. Informs when archived data can be safely deleted (for instance for public data, data may be deleted 6 years after project end date).|
|**Project**  | services  | MAY  | Text OR ResearchDriveService | Unique ID's of services associated with this project such as Virtual Machines or storage.|
|**Project**  | division  | MAY  | Text | The division linked with this project. e.g. "CIVENV"|
|**Project**  | description  | SHOULD  | Text | full description of the project.|
|**Project**  | name  | SHOULD  | Text | Title describing the project.|
|**Project**  | identifier  | MAY  | Text OR URL | additional identifiers associated with the project.|
|**Project**  | startDate  | MAY  | Date | The date this project starts.|
|**Project**  | requirements  | MAY  | Text | Free-text requirements for this projects, e.g. "requires human ethics approval".|
|**Project**  | dataClassification   | MUST   | Text | The classification of the data for [research data retention](https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-classification) and [information security](https://www.protectivesecurity.govt.nz/classification/overview).  MUST be ONE of ["Public", "Internal", "Sensitive", or "Restricted"]. Default "Sensitive".|
|**Project**  | actions   | MAY   | DeleteAction | Any delete actions indicating when data associated with this project may safely be deleted. |
|**Project**  | retentionPeriodYears   | MUST  | Number | How many years must be retained after project end date based on Data Classification or other justifications. |
|**Project**  | retentionPeriodJustification   | MAY*  | text | Reasoning for why data should be retained for a given period. MUST be included if retention period differs from standards based on data classfication |

## OrganizationRole

`OrganizationRole` MUST describe how a `Person` relates to a `Project` to understand that person's role regarding data ownership and project ownership.
`OrganizationRole`s MUST provide a `Person` via `member` and the description of role via `name`. a name of `"Project Owner"`, `"Data Owner"`  and `"Data Contact"` SHOULD indicate primary stakeholders in research data.

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**OrganizationRole**  | @id  | MUST  | Text | A value that uniquely identifies a person or a group of peoples relationship to a project|
|**OrganizationRole**  | member  | MUST  | Person | The person or persons that hold this role in this project. 
|**OrganizationRole**  | roleName | MUST | Text | A this member's role regarding project data MUST be ONE of:["CeR Contact","Contact Person","Data Contact","Data Owner","Former Team Member","Grant PI","Primary Adviser","Primary Reviewer","Project Owner","Project Team Member","Reviewer","Supervisor","Support"] default: "Project Team Member" |

## People

`Person` records in the _crate_ SHOULD provide sufficient information to uniquely identify a person within the University of Auckland system and if possible contact them regarding the data in the _crate_.

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**Person**  | @id  | MUST  | Text | A UPI that uniquely identifies this person in the University Active Directory Lookup. e.g. "pmcg006"|
|**Person**  | email  | SHOULD  | Email | an email address that may be used to contact this person.
|**Person**  | name | MAY  | Text | The full name identifying this person.

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
|**DeleteAction**  | targetCollection  | MUST  | Dataset OR ResearchDriveService | The dataset that is the target of this delete action.|
|**DeleteAction**  | actionStatus  | MUST  | ActionStatusType | Status of the deletion of the target dataset.|
|**DeleteAction**  | endTime  | MUST  | DateTime | When the deletion of the data is to occur or has occurred.|

## ResearchDriveService

The network research drive the data originated from MAY also be described using a `ResearchDriveService` object.

### Terms

| Domain | Property | Required? |type|Description|
|---|----|---|-----|---|
|**ResearchDriveService**  | allocatedGb  | MAY | Number | The total storage size on this research drive at time of archiving. in Gigabytes (not gibibytes!). |
|**ResearchDriveService**  | date  | SHOULD  | Date | The date the drive was archived at. |
|**ResearchDriveService**  | firstDay  | SHOULD | Date | The date the drive was first allocated. |
|**ResearchDriveService**  | freeGb  | MAY  | Number | The remaining storage space available on the research drive. in Gigabytes. |
|**ResearchDriveService**  | name  | MUST  | Number | The longform name of this research drive eg. "reslig202200001-Tītoki-metabolomics". |
|**ResearchDriveService**  | percentageUsed  | MAY | Number | what percentage of storage was in use for this drive. |
|**ResearchDriveService**  | project  | MUST  | Project | projects linked to this research drive. |
|**ResearchDriveService**  | usedGb  | MUST  | Number | The storage in use at time of archiving (the total size of any archive created from this research drive). in Gigabytes. |


## Example eResearch Project Archive Crate
* [ro-crate-metadata.json](exampleCrate/ro-crate-metadata.json)


```json
{
  "@context": "https://w3id.org/ro/crate/1.1/context",
  "@graph": [
    {
      "@id": "./",
      "@type": "Dataset",
      "datePublished": "2024-12-16T00:17:52+00:00",
      "mainEntity": [
{
  "@id": "#research_drive_service/reslig202200001-Tītoki-metabolomics"
}
      ]
    },
    {
      "@id": "ro-crate-metadata.json",
      "@type": "CreativeWork",
      "about": {
"@id": "./"
      },
      "conformsTo": [
{
  "@id": "https://w3id.org/ro/crate/1.1"
},
{
  "@id": "https://uoa-eresearch.github.io/Project-Archive-RoCrate-Profile/"
}
      ]
    },
    {
      "@id": "#medr894",
      "@type": "Person",
      "email": "m.edric@test.auckland.ac.nz",
      "fullName": "Melisa Edric"
    },
    {
      "@id": "#member/100/ProjectTeamMember/medr894",
      "@type": "OrganizationRole",
      "member": [
{
  "@id": "#medr894"
}
      ],
      "name": "Project Team Member"
    },
    {
      "@id": "#snic021",
      "@type": "Person",
      "email": "s.nicholas@test.auckland.ac.nz",
      "fullName": "Samina Nicholas"
    },
    {
      "@id": "#member/100/ProjectOwner/snic021",
      "@type": "OrganizationRole",
      "member": [
{
  "@id": "#snic021"
}
      ],
      "name": "Project Owner"
    },
    {
      "@id": "#research_drive_service/reslig202200001-Tītoki-metabolomics",
      "@type": "ResearchDriveService",
      "allocatedGb": 25600.0,
      "date": "2024-10-13T00:00:00",
      "firstDay": "2022-01-09T00:00:00",
      "freeGb": 24004.5,
      "name": "reslig202200001-Tītoki-metabolomics",
      "percentageUsed": 2.75578,
      "project": [
{
  "@id": "#project/100"
}
      ],
      "usedGb": 1596.0
    },
    {
      "@id": "retention_period_for/#research_drive_service/reslig202200001-Tītoki-metabolomics",
      "@type": "DeleteAction",
      "actionStatus": "PotentialActionStatus",
      "endTime": "2030-11-04T00:00:00",
      "targetCollection": [
{
  "@id": "#research_drive_service/reslig202200001-Tītoki-metabolomics"
}
      ]
    },
    {
      "@id": "#project/100",
      "@type": "ResearchProject",
      "actions": [
{
  "@id": "retention_period_for/#research_drive_service/reslig202200001-Tītoki-metabolomics"
}
      ],
      "dataClassification": "Sensitive",
      "description": "Stress in plants could be defined as any change in growth condition(s) that disrupts metabolic homeostasis and requires an adjustment of metabolic pathways in a process that is usually referred to as acclimation. Metabolomics could contribute significantly to the study of stress biology in plants and other organisms by identifying different compounds, such as by-products of stress metabolism, stress signal transduction molecules or molecules that are part of the acclimation response of plants.",
      "division": "Liggins Institute",
      "endDate": "2024-11-04T00:00:00",
      "identifier": [
"uoa00001",
"reslig202200001"
      ],
      "isCompleted": true,
      "member": [
{
  "@id": "#member/100/ProjectTeamMember/medr894"
},
{
  "@id": "#member/100/ProjectOwner/snic021"
}
      ],
      "name": "Tītoki metabolomics",
      "retentionPeriodYears": 6,
      "services": [
{
  "@id": "#research_drive_service/reslig202200001-Tītoki-metabolomics"
}
      ],
      "startDate": "2022-01-01T00:00:00",
      "updatedTime": "2024-12-16T13:17:52.290170"
    }
  ]
}

```

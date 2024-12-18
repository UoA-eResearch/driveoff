// This file is auto-generated by @hey-api/openapi-ts

/**
 * Model for project codes.
 */
export type Code = {
    id: (number | null);
    code: string;
};

/**
 * Data classification labels defined in Research
 * Data Management Policy.
 */
export type DataClassification = 'Public' | 'Internal' | 'Sensitive' | 'Restricted';

export type HTTPValidationError = {
    detail?: Array<ValidationError>;
};

/**
 * Submission data model for the POST request.
 */
export type InputDriveOffboardSubmission = {
    retentionPeriodYears: number;
    retentionPeriodJustification?: (string | null);
    dataClassification: DataClassification;
    isCompleted: boolean;
    driveName: string;
    projectChanges?: (ProjectChanges | null);
};

/**
 * Data class for the identity list in POST request.
 */
export type InputIdentity = {
    username: string;
};

/**
 * The set of result items from Project DB API.
 */
export type InputIdentityResultItems = {
    items: Array<InputIdentity>;
};

/**
 * Data class for a Person model in POST request.
 */
export type InputPerson = {
    id?: (number | null);
    'person.email': (string | null);
    'person.full_name': string;
    'person.identities': InputIdentityResultItems;
    role: Role;
};

/**
 * Input project model for data received from POST
 */
export type InputProject = {
    title: string;
    description: string;
    division: string;
    start_date: string;
    end_date: string;
    id?: (number | null);
    members: Array<InputPerson>;
    codes: Array<Code>;
    services: InputServices;
};

/**
 * Input object describing relevant storage services.
 */
export type InputServices = {
    research_drive: Array<ResearchDriveService>;
};

/**
 * SQL model for storing simple file manifests
 */
export type Manifest = {
    id: number;
    manifest: string;
};

/**
 * Public model for project members.
 */
export type MemberPublic = {
    role: Role;
    person: Person;
};

/**
 * Data class for a Person model in database.
 */
export type Person = {
    id?: (number | null);
    email: (string | null);
    full_name: string;
    username: string;
};

/**
 * Project model for data stored in database
 */
export type Project = {
    title: string;
    description: string;
    division: string;
    start_date: string;
    end_date: string;
    id?: (number | null);
};

/**
 * A model for describing updates to a project.
 */
export type ProjectChanges = {
    title?: (string | null);
    description?: (string | null);
};

/**
 * Public model for project with drive and member information.
 */
export type ProjectWithDriveMember = {
    title: string;
    description: string;
    division: string;
    start_date: string;
    end_date: string;
    id: number;
    codes: Array<Code>;
    research_drives: Array<ResearchDriveServicePublic>;
    members: Array<MemberPublic>;
};

/**
 * Object describing a research drive service.
 */
export type ResearchDriveService = {
    name: string;
    allocated_gb: number;
    free_gb: number;
    used_gb: number;
    percentage_used: number;
    date: string;
    first_day: string;
    last_day: (string | null);
    id?: (number | null);
};

/**
 * Public model for Research Drive Service.
 */
export type ResearchDriveServicePublic = {
    name: string;
    allocated_gb: number;
    free_gb: number;
    used_gb: number;
    percentage_used: number;
    date: string;
    first_day: string;
    last_day: (string | null);
    manifest: Manifest;
};

/**
 * Project roles for people.
 */
export type Role = {
    id?: (number | null);
    name: string;
};

export type ValidationError = {
    loc: Array<(string | number)>;
    msg: string;
    type: string;
};

export type SetDriveInfoApiV1ResdriveinfoPostData = {
    body: InputProject;
    query?: {
        path?: string;
    };
};

export type SetDriveInfoApiV1ResdriveinfoPostResponse = (Project);

export type SetDriveInfoApiV1ResdriveinfoPostError = (HTTPValidationError);

export type GetDriveInfoApiV1ResdriveinfoGetData = {
    query: {
        drive_id: string;
        path?: string;
    };
};

export type GetDriveInfoApiV1ResdriveinfoGetResponse = (ProjectWithDriveMember);

export type GetDriveInfoApiV1ResdriveinfoGetError = (HTTPValidationError);

export type AppendDriveInfoApiV1SubmissionPostData = {
    body: InputDriveOffboardSubmission;
    query?: {
        path?: string;
    };
};

export type AppendDriveInfoApiV1SubmissionPostResponse = ({
    [key: string]: (string);
});

export type AppendDriveInfoApiV1SubmissionPostError = (HTTPValidationError);

export type GetDriveManifestApiV1ResdrivemanifestGetData = {
    query: {
        drive_id: string;
        path?: string;
    };
};

export type GetDriveManifestApiV1ResdrivemanifestGetResponse = ({
    [key: string]: (string);
});

export type GetDriveManifestApiV1ResdrivemanifestGetError = (HTTPValidationError);
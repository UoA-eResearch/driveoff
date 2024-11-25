/**
 * Type definitions for project information. TODO - generate based on output types in Python.
 */
export interface Person {
    email: string | null;
    full_name: string;
    username: string;
}

export interface Role {
    name: string
}

export interface Member {
    person: Person;
    roles: Role[]
}

export interface Project {
    title: string
    description: string
    division: string
    members: Member[]
}

export interface ResearchDriveService {
    allocated_gb: number
    name: string
}

export enum DataClassification {
    Public = "Public",
    Internal = "Internal",
    Sensitive = "Sensitive",
    Restricted = "Restricted"
}

export interface ResDriveInfoStore {
    project: Project | null;
    drive: ResearchDriveService | null;
}

export interface FormStateStore {
    isCorrectDrive: boolean | null;
    areProjectDetailsCorrect: boolean | null;
    project: Project | null;
    dataClassification: DataClassification | null;
    retentionPeriod: number | null;
}
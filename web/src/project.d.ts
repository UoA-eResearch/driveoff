/**
 * Type definitions for project information. TODO - generate based on output types in Python.
 */
interface Person {
    email: string | null;
    full_name: string;
    username: string;
}

interface Role {
    name: string
}

interface Member {
    person: Person;
    role: Role
}

interface Project {
    title: string
    description: string
    division: string
    members: Member[]
}

interface ResearchDriveService {
    allocated_gb: number
    name: string
}
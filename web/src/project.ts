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
    used_gb: number
}

/**
 * Makes and returns an empty Project.
 * @returns An empty Project.
 */
export function makeProject(): Project {
    return {
        title: "",
        description: "",
        division: "",
        members: []
    }
}

/**
 * Given a list of members, filter for project owners.
 * @param members List of members to search through
 * @returns Members who are project owners.
 */
export function getProjectOwners(members: Member[]): Member[] {
    return members.filter(member =>
        member.roles.some(
            (role: Role) => role.name === "Project Owner"
        )
    );
}

/**
 * Given a list of project members, filter for ordinary members.
 * @param members List of members to search through
 * @returns Members who are not project owners.
 */
export function getProjectMembers(members: Member[]): Member[] {
    return members.filter(member =>
        !member.roles.some(
            (role: Role) => role.name === "Project Owner"
        )
    );
}

/**
 * Given a list of members, return a string of their names.
 * @param members Members to return names for.
 * @returns A string representing all member names.
 */
export function membersToString(members: Member[]): string {
    return members.map(member =>
        member.person.full_name
    ).join(", ");
}
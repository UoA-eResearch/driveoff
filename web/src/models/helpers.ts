/**
 * Additional methods for Members.
 */

import type { MemberPublic } from "@/client";


/**
 * Given a list of members, filter for project owners.
 * @param members List of members to search through
 * @returns Members who are project owners.
 */
export function getProjectOwners(members: MemberPublic[]): MemberPublic[] {
    return members.filter(member =>
        member.role.name === "Project Owner"
    );
}

/**
 * Given a list of project members, filter for ordinary members.
 * @param members List of members to search through
 * @returns Members who are not project owners.
 */
export function getProjectMembers(members: MemberPublic[]): MemberPublic[] {
    return members.filter(member =>
        member.role.name !== "Project Owner"
    );
}

/**
 * Given a list of members, return a string of their names.
 * @param members Members to return names for.
 * @returns A string representing all member names.
 */
export function membersToString(members: MemberPublic[]): string {

    return members.filter((_, idx, arr) =>
        // Filter for unique members
        arr.findIndex(member => member.person.email) === idx
    ).map(member =>
        member.person.full_name
    ).join(", ");
}
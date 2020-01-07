# -*- coding: utf-8 -*-
"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Classes for building models of 3D/4D polytopes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See the doc: "https://neozhaoliang.github.io/polytopes/"

"""
from itertools import combinations
import numpy as np
import helpers
from todd_coxeter import CosetTable


class BasePolytope(object):

    """
    Base class for building polyhedron and polychoron using
    Wythoff's construction.
    """

    def __init__(self, coxeter_diagram, init_dist, extra_relations=()):
        """
        parameters
        ----------
        :coxeter_diagram: Coxeter diagram for this polytope.
        :init_dist: distances between the initial vertex and the mirrors.

        :extra_relations: a presentation of a star polytope can be obtained by
            imposing more relations on the generators. For example "(ρ0ρ1ρ2ρ1)^n = 1"
            for some integer n, where n is the number of sides of a hole.
            See Coxeter's article

                "Regular skew polyhedra in three and four dimensions,
                 and their topological analogues"

        """
        # Coxeter matrix of the symmetry group
        self.coxeter_matrix = helpers.get_coxeter_matrix(coxeter_diagram)
        self.mirrors = helpers.get_mirrors(coxeter_diagram)
        # reflection transformations about the mirrors
        self.reflections = tuple(helpers.reflection_matrix(v) for v in self.mirrors)
        # the initial vertex
        self.init_v = helpers.get_init_point(self.mirrors, init_dist)
        # a mirror is active if and only if the initial vertex is off it
        self.active = tuple(bool(x) for x in init_dist)

        # generators of the symmetry group
        self.symmetry_gens = tuple(range(len(self.coxeter_matrix)))
        # relations between the generators
        self.symmetry_rels = tuple((i, j) * self.coxeter_matrix[i][j]
                                   for i, j in combinations(self.symmetry_gens, 2))

        self.symmetry_rels += tuple(extra_relations)

        # to be calculated later
        self.vtable = None
        self.num_vertices = None
        self.vertex_coords = []

        self.num_edges = None
        self.edge_indices = []
        self.edge_coords = []

        self.num_faces = None
        self.face_indices = []
        self.face_coords = []

    def build_geometry(self):
        self.get_vertices()
        self.get_edges()
        self.get_faces()

    def get_vertices(self):
        """
        This method computes the following data that will be needed later:
            1. a coset table for the symmetry group.
            2. a complete list of word representations of the symmetry group.
            3. coordinates of the vertices.
        """
        # generators of the stabilizing subgroup that fixes the initial vertex.
        vgens = [(i,) for i, active in enumerate(self.active) if not active]
        self.vtable = CosetTable(self.symmetry_gens, self.symmetry_rels, vgens)
        self.vtable.run()
        self.vwords = self.vtable.get_words()  # get word representations of the vertices
        self.num_vertices = len(self.vwords)
        # use words in the symmetry group to transform the initial vertex to other vertices.
        self.vertex_coords = tuple(self.transform(self.init_v, w) for w in self.vwords)

    def get_edges(self):
        """
        This method computes the indices and coordinates of all edges.

        1. if the initial vertex lies on the i-th mirror then the reflection
           about this mirror fixes v0 and there are no edges of type i.

        2. else v0 and its virtual image v1 about this mirror generates a base
           edge e, the stabilizing subgroup of e is generated by a single word (i,),
           again we use Todd-Coxeter's procedure to get a complete list of word
           representations for the edges of type i and use them to transform e to other edges.
        """
        for i, active in enumerate(self.active):
            if active:  # if there are edges of type i
                egens = [(i,)]  # generators of the stabilizing subgroup that fixes the base edge.
                etable = CosetTable(self.symmetry_gens, self.symmetry_rels, egens)
                etable.run()
                words = etable.get_words()  # get word representations of the edges
                elist = []
                for word in words:
                    v1 = self.move(0, word)
                    v2 = self.move(0, (i,) + word)
                    # avoid duplicates
                    if (v1, v2) not in elist and (v2, v1) not in elist:
                        elist.append((v1, v2))

                self.edge_indices.append(elist)
                self.edge_coords.append([(self.vertex_coords[x], self.vertex_coords[y])
                                         for x, y in elist])
        self.num_edges = sum(len(elist) for elist in self.edge_indices)

    def get_faces(self):
        """
        This method computes the indices and coordinates of all faces.

        The composition of the i-th and the j-th reflection is a rotation
        which fixes a base face f. The stabilizing group of f is generated
        by [(i,), (j,)].
        """
        for i, j in combinations(self.symmetry_gens, 2):
            f0 = []
            m = self.coxeter_matrix[i][j]
            fgens = [(i,), (j,)]
            if self.active[i] and self.active[j]:
                for k in range(m):
                    # rotate the base edge m times to get the base f,
                    # where m = self.coxeter_matrix[i][j]
                    f0.append(self.move(0, (i, j) * k))
                    f0.append(self.move(0, (j,) + (i, j) * k))
            elif (self.active[i] or self.active[j]) and m > 2:
                for k in range(m):
                    f0.append(self.move(0, (i, j) * k))
            else:
                continue

            ftable = CosetTable(self.symmetry_gens, self.symmetry_rels, fgens)
            ftable.run()
            words = ftable.get_words()
            flist = []
            for word in words:
                f = tuple(self.move(v, word) for v in f0)
                if not helpers.check_duplicate_face(f, flist):
                    flist.append(f)

            self.face_indices.append(flist)
            self.face_coords.append([tuple(self.vertex_coords[x] for x in face)
                                     for face in flist])

        self.num_faces = sum(len(flist) for flist in self.face_indices)

    def transform(self, vector, word):
        """Transform a vector by a word in the symmetry group.
        """
        for w in word:
            vector = np.dot(vector, self.reflections[w])
        return vector

    def move(self, vertex, word):
        """Transform a vertex by a word in the symmetry group.
           Return the index of the resulting vertex.
        """
        for w in word:
            vertex = self.vtable[vertex][w]
        return vertex

    def get_latex_format(self, symbol=r"\rho", cols=3, snub=False):
        """Return the words of the vertices in latex format.
           `cols` is the number of columns of the output latex array.
        """
        def to_latex(word):
            if not word:
                return "e"
            else:
                if snub:
                    return "".join(symbol + "_{{{}}}".format(i // 2) for i in word)
                else:
                    return "".join(symbol + "_{{{}}}".format(i) for i in word)

        latex = ""
        for i, word in enumerate(self.vwords):
            if i > 0 and i % cols == 0:
                latex += r"\\"
            latex += to_latex(word)
            if i % cols != cols - 1:
                latex += "&"

        return r"\begin{{array}}{{{}}}{}\end{{array}}".format("l" * cols, latex)


class Polyhedra(BasePolytope):
    """
    Base class for 3d polyhedron.
    """

    def __init__(self, coxeter_diagram, init_dist, extra_relations=()):
        if not len(coxeter_diagram) == len(init_dist) == 3:
            raise ValueError("Length error: the inputs must all have length 3")
        super().__init__(coxeter_diagram, init_dist, extra_relations)


class Snub(Polyhedra):
    """
    A snub polyhedra is generated by the subgroup that consists of only
    rotations in the full symmetry group. This subgroup has presentation

        <r, s | r^p = s^q = (rs)^2 = 1>

    where r = ρ0ρ1, s = ρ1ρ2 are two rotations.
    Again we solve all words in this subgroup and then use them to
    transform the initial vertex to get all vertices.
    """

    def __init__(self, coxeter_diagram, init_dist=(1.0, 1.0, 1.0)):
        super().__init__(coxeter_diagram, init_dist, extra_relations=())
        # the representaion is not in the form of a Coxeter group,
        # we must overwrite the relations.
        self.symmetry_gens = (0, 1, 2, 3)
        self.symmetry_rels = ((0,) * self.coxeter_matrix[0][1],
                              (2,) * self.coxeter_matrix[1][2],
                              (0, 2) * self.coxeter_matrix[0][2],
                              (0, 1), (2, 3))
        # order of the generator rotations
        self.rotations = {(0,): self.coxeter_matrix[0][1],
                          (2,): self.coxeter_matrix[1][2],
                          (0, 2): self.coxeter_matrix[0][2]}

    def get_vertices(self):
        self.vtable = CosetTable(self.symmetry_gens, self.symmetry_rels, coxeter=False)
        self.vtable.run()
        self.vwords = self.vtable.get_words()
        self.num_vertices = len(self.vwords)
        self.vertex_coords = tuple(self.transform(self.init_v, w) for w in self.vwords)

    def get_edges(self):
        for rot in self.rotations:
            elist = []
            e0 = (0, self.move(0, rot))
            for word in self.vwords:
                e = tuple(self.move(v, word) for v in e0)
                if e not in elist and e[::-1] not in elist:
                    elist.append(e)

            self.edge_indices.append(elist)
            self.edge_coords.append([(self.vertex_coords[i], self.vertex_coords[j])
                                     for i, j in elist])
        self.num_edges = sum(len(elist) for elist in self.edge_indices)

    def get_faces(self):
        orbits = (tuple(self.move(0, (0,) * k) for k in range(self.rotations[(0,)])),
                  tuple(self.move(0, (2,) * k) for k in range(self.rotations[(2,)])),
                  (0, self.move(0, (2,)), self.move(0, (0, 2))))
        for f0 in orbits:
            flist = []
            for word in self.vwords:
                f = tuple(self.move(v, word) for v in f0)
                if not helpers.check_duplicate_face(f, flist):
                    flist.append(f)

            self.face_indices.append(flist)
            self.face_coords.append([tuple(self.vertex_coords[v] for v in face)
                                     for face in flist])

        self.num_faces = sum([len(flist) for flist in self.face_indices])

    def transform(self, vertex, word):
        for g in word:
            if g == 0:
                vertex = np.dot(vertex, self.reflections[0])
                vertex = np.dot(vertex, self.reflections[1])
            else:
                vertex = np.dot(vertex, self.reflections[1])
                vertex = np.dot(vertex, self.reflections[2])
        return vertex


class Polychora(BasePolytope):
    """
    Base class for 4d polychoron.
    """

    def __init__(self, coxeter_diagram, init_dist, extra_relations=()):
        if not (len(coxeter_diagram) == 6 and len(init_dist) == 4):
            raise ValueError("Length error: the input coxeter_diagram must have length 6 and init_dist has length 4")
        super().__init__(coxeter_diagram, init_dist, extra_relations)


class Snub24Cell(Polychora):
    """The snub 24-cell can be constructed from snub demitesseract [3^(1,1,1)]+,
       the procedure is similar with snub polyhedron above.
       Its symmetric group is generated by three rotations {r, s, t}, a presentation
       is
           G = <r, s, t | r^3 = s^3 = t^3 = (rs)^2 = (rt)^2 = (s^-1 t)^2 = 1>

       where r = ρ0ρ1, s = ρ1ρ2, t = ρ1ρ3.
    """

    def __init__(self):
        coxeter_diagram = (3, 2, 2, 3, 3, 2)
        active = (1, 1, 1, 1)
        super().__init__(coxeter_diagram, active, extra_relations=())
        self.symmetry_gens = tuple(range(6))
        self.symmetry_rels = ((0,) * 3, (2,) * 3, (4,) * 3,
                              (0, 2) * 2, (0, 4) * 2, (3, 4) * 2,
                              (0, 1), (2, 3), (4, 5))
        self.rotations = ((0,), (2,), (4,), (0, 2), (0, 4), (3, 4))

    def get_vertices(self):
        self.vtable = CosetTable(self.symmetry_gens, self.symmetry_rels, coxeter=False)
        self.vtable.run()
        self.vwords = self.vtable.get_words()
        self.num_vertices = len(self.vwords)
        self.vertex_coords = tuple(self.transform(self.init_v, w) for w in self.vwords)

    def get_edges(self):
        for rot in self.rotations:
            elist = []
            e0 = (0, self.move(0, rot))
            for word in self.vwords:
                e = tuple(self.move(v, word) for v in e0)
                if e not in elist and e[::-1] not in elist:
                    elist.append(e)

            self.edge_indices.append(elist)
            self.edge_coords.append([(self.vertex_coords[i], self.vertex_coords[j])
                                     for i, j in elist])
        self.num_edges = sum(len(elist) for elist in self.edge_indices)

    def get_faces(self):
        orbits = (tuple(self.move(0, (0,) * k) for k in range(3)),
                  tuple(self.move(0, (2,) * k) for k in range(3)),
                  tuple(self.move(0, (4,) * k) for k in range(3)),
                  (0, self.move(0, (2,)), self.move(0, (0, 2))),
                  (0, self.move(0, (4,)), self.move(0, (0, 4))),
                  (0, self.move(0, (2,)), self.move(0, (5, 2))),
                  (0, self.move(0, (0, 2)), self.move(0, (5, 2))))
        for f0 in orbits:
            flist = []
            for word in self.vwords:
                f = tuple(self.move(v, word) for v in f0)
                if not helpers.check_duplicate_face(f, flist):
                    flist.append(f)

            self.face_indices.append(flist)
            self.face_coords.append([tuple(self.vertex_coords[v] for v in face)
                                     for face in flist])

        self.num_faces = sum([len(flist) for flist in self.face_indices])

    def transform(self, vertex, word):
        for g in word:
            if g == 0:
                vertex = np.dot(vertex, self.reflections[0])
                vertex = np.dot(vertex, self.reflections[1])
            elif g == 2:
                vertex = np.dot(vertex, self.reflections[1])
                vertex = np.dot(vertex, self.reflections[2])
            else:
                vertex = np.dot(vertex, self.reflections[1])
                vertex = np.dot(vertex, self.reflections[3])
        return vertex


class Catalan3D(object):
    """Construct the dual 3d Catalan solid from a given uniform polytope.
       The computation of edges and faces of this dual shape are all done
       with integer arithmetic so floating comparison is avoided.
    """
    def __init__(self, P):
        """`P`: a 3d polyhedra.
        """
        if len(P.coxeter_matrix) != 3:
            raise ValueError("A 3d polyhedra is expected")
        self.P = P

        self.num_vertices = None
        self.vertex_coords = []  # [[v1, v2, ...], [v_k, ...]]
        self.vertex_coords_flatten = []  # [v1, v2, ..., vk, ...]

        self.num_edges = None
        self.edge_indices = []

        self.num_faces = None
        self.face_indices = []

    def build_geometry(self):
        self.P.build_geometry()
        self.num_vertices = self.P.num_faces
        self.num_edges = self.P.num_edges
        self.num_faces = self.P.num_vertices
        self.get_vertices()
        self.get_edges()
        self.get_faces()

    def get_vertices(self):
        """The vertices in the Catalan solid are in one-to-one correspondence
           with P's faces.
        """
        for flist in self.P.face_coords:
            vlist = []
            for face in flist:
                # for each face of P, compute the normal of P
                normal = helpers.get_face_normal(face)
                # compute the dot of the vertices with the normal
                inn = sum([np.dot(normal, p) for p in face]) / len(face)
                # divide the reciprocal, this is the vertex of the dual solid
                v = normal / inn
                vlist.append(v)
                self.vertex_coords_flatten.append(v)

            self.vertex_coords.append(vlist)

    def get_edges(self):
        """Two face centers are connected by an edge if and only if
           their faces are adjacent in P.
        """
        P_faces_flatten = [face for flist in self.P.face_indices for face in flist]
        for elist_P in self.P.edge_indices:
            elist = []
            for eP in elist_P:
                e = helpers.find_face_by_edge(eP, P_faces_flatten)
                if e is not None:
                    elist.append(e)
            self.edge_indices.append(elist)

    def get_faces(self):
        """A set of face centers form a face in the Catalan solid if and
           only if their faces surround a common vertex in P.
        """
        P_faces_flatten = [face for flist in self.P.face_indices for face in flist]
        for v in range(self.P.num_vertices):
            # for each vertex of v of P, find P' faces that surround v, their indices
            # are stored in f.
            f = []
            for i, face in enumerate(P_faces_flatten):
                if v in face:
                    f.append(i)
            # the faces in f may not be in the right order,
            # rearrange them so that f0 and f1 are adjacent, f1 and f2 are adjacent, ... etc.
            nsides = len(f)
            v0 = f[0]
            new_face = [v0]
            visited = set([v0])
            while len(new_face) < nsides:
                v = new_face[-1]
                for u in f:
                    if u not in visited and helpers.has_common_edge(P_faces_flatten[v], P_faces_flatten[u]):
                        new_face.append(u)
                        visited.add(u)
                        break

            self.face_indices.append(tuple(new_face))


class Polytope5D(BasePolytope):

    def __init__(self, coxeter_diagram, init_dist, extra_relations=()):
        if len(coxeter_diagram) != 10 and len(init_dist) != 5:
            raise ValueError("wrong input dimensions")
        super().__init__(coxeter_diagram, init_dist, extra_relations)

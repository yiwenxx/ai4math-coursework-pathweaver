import PathWeaverFormal.TwoDigitCyclicLift
import Lean.Elab.Tactic.Grind

namespace PathWeaverFormal.Jsp158.FreePosition

private abbrev Along (f : Nat → Nat) (a d : Nat) :=
  AtLeastThreeColors (f a) (f (a+d)) (f (a+2*d)) (f (a+3*d))

private theorem decode (D : Nat → Nat) (g : Nat → Nat) {a d : Nat}
    (h : Along (fun z => D (g z)) a d) : Along g a d := by
  unfold Along AtLeastThreeColors at *
  grind

/-- Any constant replacement at the zero residue is legal. -/
def FreeAtZero (p : Nat) (f : Nat → Nat) : Prop :=
  ∀ v : Nat, CyclicThreeColors p (fun z => if z=0 then v else f z)

private theorem outsideZero {p : Nat} {f g : Nat → Nat} (free : FreeAtZero p f)
    (agree : ∀ z, z%p≠0 → g z=f (z%p)) (a d : Nat) (hd : d%p≠0) : Along g a d := by
  apply Classical.byContradiction
  intro bad
  have two : ∃ u v, (g a=u ∨ g a=v) ∧ (g (a+d)=u ∨ g (a+d)=v) ∧
      (g (a+2*d)=u ∨ g (a+2*d)=v) ∧ (g (a+3*d)=u ∨ g (a+3*d)=v) := by
    unfold Along AtLeastThreeColors at bad
    by_cases b : g a=g (a+d)
    · by_cases c : g a=g (a+2*d)
      · exact ⟨g a,g (a+3*d),by grind⟩
      · exact ⟨g a,g (a+2*d),by grind⟩
    · exact ⟨g a,g (a+d),by grind⟩
  obtain ⟨u,v,ha,hb,hc,he⟩ := two
  let patched (z : Nat) := if z%p=0 then u else f (z%p)
  have mem (z : Nat) (h : g z=u ∨ g z=v) : patched z=u ∨ patched z=v := by
    by_cases hz : z%p=0
    · simp [patched,hz]
    · simpa only [patched,ite_eq_right hz,← agree z hz] using h
  have ok : Along patched a d := free u a d hd
  have := mem _ ha; have := mem _ hb; have := mem _ hc; have := mem _ he
  unfold Along AtLeastThreeColors at ok
  grind

private theorem digits {p d : Nat} (hp : 0<p) (hd : d%p=0) (a k : Nat) :
    (a+k*d)%p=a%p ∧ (a+k*d)/p=a/p+k*(d/p) := by
  have eq : p*(d/p)=d := by simpa [hd] using Nat.mod_add_div d p
  have shift : a+k*d=a+p*(k*(d/p)) := by rw [← Nat.mul_left_comm k p (d/p),eq]
  exact ⟨by rw [shift,Nat.add_mul_mod_self_left], by rw [shift,Nat.add_mul_div_left _ _ hp]⟩

private theorem inColumn {p a d : Nat} (hp : 0<p) (hd : d%p=0) (g c : Nat → Nat)
    (same : ∀ z, z%p=a%p → g z=c (z/p)) (ok : Along c (a/p) (d/p)) : Along g a d := by
  have eq (k : Nat) : g (a+k*d)=c (a/p+k*(d/p)) :=
    (same _ (digits hp hd a k).1).trans (congrArg c (digits hp hd a k).2)
  simpa only [Along, same a rfl, show g (a+d)=c (a/p+d/p) by simpa using eq 1,
    eq 2,eq 3] using ok

private def enlarged (c : Nat → Nat) (z : Nat) := z%3+3*c (z/3)

private theorem enlarged_good {n : Nat} (hn : 0<n) (c : Nat → Nat)
    (good : ∀ a d, 0<d → a+3*d<n → Along c a d) (a d : Nat) (hd : 0<d)
    (endpt : a+3*d≤n) : Along (enlarged c) a d := by
  by_cases h : d%3=0
  · apply decode (fun z => z/3)
    apply inColumn (by decide : 0<3) h _ c
    · intro z _
      simp only [enlarged,Nat.add_mul_div_left _ _ (by decide : 0<3),
        Nat.div_eq_of_lt (Nat.mod_lt _ (by decide : 0<3)),Nat.zero_add]
    · apply good _ _ (by omega)
      have := (digits (by decide : 0<3) h a 3).2
      omega
  · apply decode (fun z => z%3)
    have eq (z : Nat) : enlarged c z%3=z%3 := by simp [enlarged]
    simp only [Along,eq]
    exact Or.inl ⟨by omega,by omega,by omega⟩

private theorem below {x y r s : Nat} (hx : x<r) (hy : y<s) : x+r*y<r*s :=
  Nat.lt_of_lt_of_le (show x+r*y<r*(y+1) by rw [Nat.mul_succ]; omega) (Nat.mul_le_mul_left _ hy)

/-- An arbitrary s-color interval tail and an r-color cyclic template with
a free zero residue give an r*s-color array on p*n+1 points. -/
theorem interval {p r s : Nat} (hp : 0<p) (hr : 3≤r) (f : Nat → Nat)
    (bound : ∀ x, x<p → f x<r) (free : FreeAtZero p f) (tail : Array Nat)
    (hn : 0<tail.size) (legal : IsFourAPFree3 tail) (bounded : AllColorsBelow tail s) :
    ∃ colors : Array Nat, colors.size=p*tail.size+1 ∧ IsFourAPFree3 colors ∧ AllColorsBelow colors (r*s) := by
  let c := getColor tail
  let C (z : Nat) := if z%p=0 then enlarged c (z/p) else f (z%p)+r*c (z/p)
  have low (z : Nat) (ne : z%p≠0) : C z%r=f (z%p) := by
    simp only [C,ite_eq_right ne,Nat.add_mul_mod_self_left,Nat.mod_eq_of_lt (bound _ (Nat.mod_lt _ hp))]
  have high (z : Nat) (ne : z%p≠0) : C z/r=c (z/p) := by
    simp only [C,ite_eq_right ne,Nat.add_mul_div_left _ _ (show 0<r by omega),
      Nat.div_eq_of_lt (bound _ (Nat.mod_lt _ hp)),Nat.zero_add]
  have strict (z : Nat) (hz : z≤p*tail.size) (ne : z%p≠0) : z/p<tail.size := by
    apply (Nat.div_lt_iff_lt_mul hp).2
    rw [Nat.mul_comm]
    exact Nat.lt_of_le_of_ne hz (by intro eq; simp [eq] at ne)
  let colors := Array.ofFn (fun i : Fin (p*tail.size+1) => C i.val)
  have size : colors.size=p*tail.size+1 := by simp [colors]
  have entry (z : Nat) (hz : z<p*tail.size+1) : getColor colors z=C z := by simp [colors,getColor,hz]
  refine ⟨colors,size,?_,?_⟩
  · intro a d hd last
    rw [size] at last
    rw [entry a (by omega),entry (a+d) (by omega),entry (a+2*d) (by omega),entry (a+3*d) last]
    by_cases h : d%p=0
    · have decomp : p*(d/p)=d := by simpa [h] using Nat.mod_add_div d p
      have pos : 0<d/p := by
        apply Nat.pos_of_ne_zero; intro e; simp [e] at decomp; omega
      have lastQ := (digits hp h a 3).2
      by_cases zero : a%p=0
      · apply inColumn hp h C (enlarged c) (by intro z hz; simp [C,hz,zero])
        apply enlarged_good hn c legal _ _ pos
        rw [← lastQ]; exact Nat.div_le_of_le_mul (by omega)
      · apply decode (fun z => z/r)
        apply inColumn hp h _ c (fun z hz => high z (by rwa [hz]))
        apply legal _ _ pos
        rw [← lastQ]
        exact strict _ (by omega) (by rwa [(digits hp h a 3).1])
    · exact decode (fun z => z%r) C (outsideZero free low a d h)
  · intro z hz
    rw [size] at hz
    rw [entry z hz]
    by_cases h : z%p=0
    · simp only [C,h,ite_true,enlarged]
      have le : z/p≤tail.size := Nat.div_le_of_le_mul (by omega)
      exact Nat.lt_of_lt_of_le (below (Nat.mod_lt _ (by decide : 0<3)) (bounded _ (by omega)))
        (Nat.mul_le_mul_right s hr)
    · simp only [C,ite_eq_right h]
      exact below (bound _ (Nat.mod_lt _ hp)) (bounded _ (strict _ (by omega) h))

end PathWeaverFormal.Jsp158.FreePosition
